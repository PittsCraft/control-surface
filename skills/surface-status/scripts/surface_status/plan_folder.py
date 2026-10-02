"""The plan folder on disk: paths, numbering, content hashes, slice markers, fenced blocks.

The script computes every derived value itself (ADR 0012), and this module is where it does: the
hash of a file, the next number of a report, the slices and the gates `plan.md` declares. It also
reads the one list a reviewer leaves for the script: the changed files of the critical zones, in
`conformity.md`. Paths written into the journal are relative to the plan folder and use `/`,
whatever the platform.
"""

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import assert_never

from surface_status.events import (
    Abandoned,
    AmendmentReceived,
    Blocked,
    BreakSuspected,
    CheckDone,
    Conformant,
    Event,
    FixDone,
    GatesRun,
    InterviewClosed,
    PlanAmended,
    PlanApproved,
    PlanChangeAccepted,
    PlanChangeProposed,
    PlanChangeRefused,
    PlanDrafted,
    PlanOpened,
    Resumed,
    ReviewDone,
    SliceDone,
    SuspicionDismissed,
)
from surface_status.journal import read_events

BLUEPRINT = "blueprint.md"
PLAN = "plan.md"
JOURNAL = "journal.jsonl"

_MARKER = re.compile(r"<!--\s*slice:\s*(?P<number>\S*?)\s*-->")
_NUMBER = re.compile(r"[1-9][0-9]*")
GATES_TAG = "gates"
CRITICAL_FILES_TAG = "critical-files"
_FENCE_CLOSE = re.compile(r"```[ \t]*")
_LINE_BREAK = re.compile(r"\r\n|\n|\r")


class PlanFolderError(ValueError):
    pass


class SliceMarkerError(PlanFolderError):
    pass


class GatesBlockError(PlanFolderError):
    pass


class CriticalFilesError(PlanFolderError):
    pass


def content_hash(data: bytes) -> str:
    """Hash the bytes with CRLF read as LF, so a Windows checkout hashes alike."""
    return "sha256:" + sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def parse_slice_markers(text: str) -> tuple[int, ...]:
    """List the slice numbers of the `<!-- slice:N -->` markers, in order of appearance.

    A marker is a whole line, starting at column 0. Anything else in the text, in any language, is
    ignored. A duplicated number, or a marker whose number is not a positive whole number, is an
    error: a slice number is never reused.
    """
    numbers: list[int] = []
    for number, line in enumerate(_LINE_BREAK.split(text), start=1):
        found = _MARKER.fullmatch(line)
        if found is None:
            continue
        raw = found["number"]
        if _NUMBER.fullmatch(raw) is None:
            message = f"line {number}: {line!r} is not a slice marker with a positive number"
            raise SliceMarkerError(message)
        value = int(raw)
        if value in numbers:
            message = f"line {number}: slice {value} is declared twice"
            raise SliceMarkerError(message)
        numbers.append(value)
    return tuple(numbers)


def _block_lines(
    text: str, tag: str, once: str, error: type[PlanFolderError]
) -> list[tuple[int, str]] | None:
    """Read the lines of the fenced block a tag opens, each with its number; None without one.

    The block is a fenced code block whose opening line is three backticks and the tag, at column
    0, and whose closing line is three backticks. Blank lines are skipped and each other line
    comes stripped. A second block, or one that is never closed, is an error: `once` says why.
    """
    opening = re.compile(rf"```{re.escape(tag)}[ \t]*")
    lines: list[tuple[int, str]] = []
    opened: int | None = None
    found = False
    for number, line in enumerate(_LINE_BREAK.split(text), start=1):
        if opened is None:
            if opening.fullmatch(line) is None:
                continue
            if found:
                message = f"line {number}: a second {tag} block; {once}"
                raise error(message)
            opened, found = number, True
        elif _FENCE_CLOSE.fullmatch(line) is not None:
            opened = None
        elif line.strip():
            lines.append((number, line.strip()))
    if opened is not None:
        message = f"line {opened}: the {tag} block is not closed by a line of three backticks"
        raise error(message)
    return lines if found else None


def parse_gates(text: str) -> tuple[str, ...] | None:
    """Read the commands of the `gates` block, one per line, in order; None when there is none.

    The block is a fenced code block whose opening line is exactly ```` ```gates ````, at column 0,
    and whose closing line is ```` ``` ````. Blank lines are skipped and each other line, stripped,
    is one command. An empty block says the project has no gate command. A second block, or one
    that is never closed, is an error: the plan names its gates once.
    """
    lines = _block_lines(text, GATES_TAG, "the plan names its gates once", GatesBlockError)
    return None if lines is None else tuple(command for _, command in lines)


def _stays_inside(relative: str) -> bool:
    """Whether a name written with `/` is a relative path that never leaves the folder it is in."""
    return not (
        not relative
        or "\\" in relative
        or PurePosixPath(relative).is_absolute()
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    )


def parse_critical_files(text: str) -> tuple[str, ...] | None:
    """Read the paths of the `critical-files` block, one per line, in order; None without one.

    The block is fenced like the gates block, with its own tag: ```` ```critical-files ````. Each
    line is the path of a file from the root of the repository, written with `/`; a path given
    twice is listed once. No block and an empty one both say the branch changed no file of a
    critical zone. A line that is no such path is an error, as are a second block and one that is
    never closed: a file the developer must read is never dropped in silence.
    """
    once = "the changed files of the critical zones are listed once"
    lines = _block_lines(text, CRITICAL_FILES_TAG, once, CriticalFilesError)
    if lines is None:
        return None
    paths: list[str] = []
    for number, path in lines:
        if not _stays_inside(path):
            message = f"line {number}: {path!r} is not the path of a file inside the repository"
            raise CriticalFilesError(message)
        if path not in paths:
            paths.append(path)
    return tuple(paths)


def check_name(rev: int, n: int) -> str:
    return f"checks/rev-{rev:02d}-{n:02d}.md"


def review_name(n: int) -> str:
    return f"reviews/pass-{n:02d}.md"


def suspicion_name(n: int) -> str:
    return f"reviews/suspicion-{n:02d}.md"


def gate_run_name(n: int) -> str:
    return f"gates/run-{n:02d}.txt"


def plan_change_name(n: int) -> str:
    return f"plan-changes/{n:02d}.md"


def cited_files(event: Event) -> tuple[str, ...]:  # noqa: C901, PLR0911 (one arm per event)
    """List the files of the plan folder an event points at, relative to it (ADR 0012).

    `blueprint.md` and `plan.md` count when the event carries their hash.
    """
    match event:
        case CheckDone():
            return (event.report, BLUEPRINT, PLAN)
        case PlanDrafted():
            return (BLUEPRINT, PLAN)
        case PlanApproved():
            return (BLUEPRINT,)
        case PlanAmended():
            return (PLAN,)
        case SuspicionDismissed():
            return (event.report,)
        case PlanChangeProposed() | PlanChangeAccepted() | PlanChangeRefused():
            return (event.proposal,)
        case GatesRun():
            return (gate_run_name(event.run),)
        case ReviewDone():
            return (event.report,) if event.proposal is None else (event.report, event.proposal)
        case Conformant():
            return (event.conformity, BLUEPRINT)
        case (
            PlanOpened()
            | InterviewClosed()
            | AmendmentReceived()
            | SliceDone()
            | BreakSuspected()
            | FixDone()
            | Blocked()
            | Resumed()
            | Abandoned()
        ):
            return ()
        case _:
            assert_never(event)


@dataclass(frozen=True, slots=True)
class PlanFolder:
    root: Path

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def journal(self) -> Path:
        return self.root / JOURNAL

    @property
    def blueprint(self) -> Path:
        return self.root / BLUEPRINT

    @property
    def plan(self) -> Path:
        return self.root / PLAN

    def path(self, relative: str) -> Path:
        """Resolve a name from the journal, refusing anything that leaves the folder."""
        if not _stays_inside(relative):
            message = f"{relative!r} is not a path inside the plan folder"
            raise PlanFolderError(message)
        return self.root.joinpath(*PurePosixPath(relative).parts)

    def is_file(self, relative: str) -> bool:
        """Whether a cited name is a regular file of the folder, symbolic links included."""
        try:
            target = self.path(relative).resolve(strict=True)
        except (PlanFolderError, OSError):
            return False
        return target.is_file() and target.is_relative_to(self.root.resolve())

    def file_hash(self, relative: str) -> str | None:
        """Hash of a file of the folder, None when it does not exist."""
        try:
            return content_hash(self.path(relative).read_bytes())
        except (FileNotFoundError, IsADirectoryError):
            return None

    def blueprint_hash(self) -> str | None:
        return self.file_hash(BLUEPRINT)

    def plan_hash(self) -> str | None:
        return self.file_hash(PLAN)

    def _plan_text(self) -> str:
        try:
            return self.plan.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            message = f"{PLAN} cannot be read: {error}"
            raise PlanFolderError(message) from error

    def declared_slices(self) -> tuple[int, ...]:
        """Read the slices `plan.md` declares by its markers."""
        return parse_slice_markers(self._plan_text())

    def declared_gates(self) -> tuple[str, ...] | None:
        """Read the commands the `gates` block of `plan.md` names; None when it has none."""
        return parse_gates(self._plan_text())

    def critical_files(self, relative: str) -> tuple[str, ...]:
        """Read the files the `critical-files` block of a `conformity.md` lists; none without one.

        `relative` is the proof of conformity a `conformant` event cites. Raises `PlanFolderError`
        when the file cannot be read or its block is malformed, naming the file.
        """
        try:
            text = self.path(relative).read_text(encoding="utf-8")
            return parse_critical_files(text) or ()
        except CriticalFilesError as error:
            message = f"{relative}: {error}"
            raise CriticalFilesError(message) from error
        except (OSError, UnicodeDecodeError) as error:
            message = f"{relative} cannot be read: {error}"
            raise PlanFolderError(message) from error

    def _highest(self, directory: str, pattern: re.Pattern[str], group: str) -> int:
        folder = self.root / directory
        if not folder.is_dir():
            return 0
        found = (pattern.fullmatch(entry.name) for entry in folder.iterdir())
        return max((int(match[group]) for match in found if match), default=0)

    def next_check(self, rev: int) -> str:
        """Name the report of the next cross-check of a revision: `checks/rev-NN-MM.md`."""
        pattern = re.compile(rf"rev-0*{rev}-(?P<n>[0-9]+)\.md")
        return check_name(rev, self._highest("checks", pattern, "n") + 1)

    def next_review(self) -> str:
        return review_name(self._highest("reviews", re.compile(r"pass-(?P<n>[0-9]+)\.md"), "n") + 1)

    def next_suspicion(self) -> str:
        pattern = re.compile(r"suspicion-(?P<n>[0-9]+)\.md")
        return suspicion_name(self._highest("reviews", pattern, "n") + 1)

    def next_gate_run(self) -> int:
        """Give the next gate run a number past every run recorded and every report left.

        The journal decides, so a report deleted after its run never frees its number. A report
        no line records yet, left by a run whose record was refused or cut short, is passed over
        too: a run never overwrites a report.
        """
        recorded = (event.run for event in read_events(self.journal) if isinstance(event, GatesRun))
        left = self._highest("gates", re.compile(r"run-(?P<n>[0-9]+)\.txt"), "n")
        return max(max(recorded, default=0), left) + 1

    def next_plan_change(self) -> str:
        pattern = re.compile(r"(?P<n>[0-9]+)\.md")
        return plan_change_name(self._highest("plan-changes", pattern, "n") + 1)
