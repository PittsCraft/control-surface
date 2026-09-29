"""The plan folder on disk: paths, numbering, content hashes, slice markers.

The script computes every derived value itself (ADR 0012), and this module is where it does: the
hash of a file, the next number of a report, the slices `plan.md` declares. Paths written into the
journal are relative to the plan folder and use `/`, whatever the platform.
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
    Conform,
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

OVERVIEW = "overview.md"
PLAN = "plan.md"
JOURNAL = "journal.jsonl"

_MARKER = re.compile(r"<!--\s*slice:\s*(?P<number>\S*?)\s*-->")
_NUMBER = re.compile(r"[1-9][0-9]*")
_LINE_BREAK = re.compile(r"\r\n|\n|\r")


class PlanFolderError(ValueError):
    pass


class SliceMarkerError(PlanFolderError):
    pass


def content_hash(data: bytes) -> str:
    """Hash the bytes with CRLF read as LF, so a Windows checkout hashes alike (ADR 0013)."""
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

    `overview.md` and `plan.md` count when the event carries their hash.
    """
    match event:
        case CheckDone():
            return (event.report, OVERVIEW, PLAN)
        case PlanDrafted():
            return (OVERVIEW, PLAN)
        case PlanApproved():
            return (OVERVIEW,)
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
        case Conform():
            return (event.conformity, OVERVIEW)
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
    def overview(self) -> Path:
        return self.root / OVERVIEW

    @property
    def plan(self) -> Path:
        return self.root / PLAN

    def path(self, relative: str) -> Path:
        """Resolve a name from the journal, refusing anything that leaves the folder."""
        pure = PurePosixPath(relative)
        if (
            not relative
            or "\\" in relative
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))
        ):
            message = f"{relative!r} is not a path inside the plan folder"
            raise PlanFolderError(message)
        return self.root.joinpath(*pure.parts)

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

    def overview_hash(self) -> str | None:
        return self.file_hash(OVERVIEW)

    def plan_hash(self) -> str | None:
        return self.file_hash(PLAN)

    def declared_slices(self) -> tuple[int, ...]:
        """Read the slices `plan.md` declares by its markers."""
        try:
            text = self.plan.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            message = f"{PLAN} cannot be read: {error}"
            raise PlanFolderError(message) from error
        return parse_slice_markers(text)

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
        return self._highest("gates", re.compile(r"run-(?P<n>[0-9]+)\.txt"), "n") + 1

    def next_plan_change(self) -> str:
        pattern = re.compile(r"(?P<n>[0-9]+)\.md")
        return plan_change_name(self._highest("plan-changes", pattern, "n") + 1)
