"""Record an event: replay, admit, check the disk, append (ADR 0012).

This is the only code that appends to a journal. Every step before the append only reads, so a
refusal leaves the journal byte for byte as it was, and an acceptance adds exactly one line. A
`conform` is the one event checked against git too: the files its `conformity.md` leaves the
developer to read must be files the branch changed.
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from surface_status import gitops
from surface_status.events import Conform, Event, PlanAmended, PlanDrafted
from surface_status.guards import (
    Accepted,
    DiskFacts,
    RecordContext,
    Refusal,
    admit,
    disk_guards,
    fold,
)
from surface_status.journal import TIMESTAMP_FORMAT, JournalLine, append_line, read_events
from surface_status.machine import PlanState
from surface_status.plan_folder import PlanFolder, PlanFolderError, cited_files
from surface_status.settings import Settings


def load_state(folder: PlanFolder) -> PlanState | None:
    """Replay the journal of a plan folder. None when it has no journal yet.

    Raises `JournalError` on a line that does not decode and `InvalidJournalError` on one the
    machine refuses.
    """
    return fold(read_events(folder.journal))


def timestamp(now: datetime) -> str:
    if now.tzinfo is None:
        message = "the time of a record must carry a time zone"
        raise ValueError(message)
    return now.astimezone(UTC).strftime(TIMESTAMP_FORMAT)


def _critical_files_problem(folder: PlanFolder, event: Conform, root: Path | None) -> str | None:
    """Say why the critical-files block of the cited `conformity.md` cannot be taken, if so.

    Which files a critical zone covers is the reviewer's reading; that the branch changed a file
    is a fact of git, so the script checks it: each listed path is one the branch added, modified
    or deleted against its merge base with the main branch. Outside a git work tree, or without a
    project root, there is no branch to ask and the form of the block alone is checked.
    """
    try:
        listed = folder.critical_files(event.conformity)
    except PlanFolderError as error:
        return str(error)
    if not listed or root is None or not gitops.is_work_tree(root):
        return None
    changed = gitops.changed_files(root, gitops.merge_base(root, gitops.main_ref(root)))
    unchanged = [path for path in listed if path not in changed]
    if not unchanged:
        return None
    return (
        f"{event.conformity}: the critical-files block lists a file the branch did not change: "
        + ", ".join(unchanged)
    )


def _disk_facts(folder: PlanFolder, event: Event, root: Path | None) -> DiskFacts:
    facts = DiskFacts(
        missing_files=tuple(name for name in cited_files(event) if not folder.is_file(name)),
        blueprint_hash=folder.blueprint_hash(),
        plan_hash=folder.plan_hash(),
        slices=None,
    )
    if isinstance(event, PlanDrafted | PlanAmended):
        try:
            facts = replace(facts, slices=folder.declared_slices())
        except PlanFolderError as error:
            facts = replace(facts, slices_problem=str(error))
        try:
            facts = replace(facts, gates=folder.declared_gates())
        except PlanFolderError as error:
            facts = replace(facts, gates_problem=str(error))
    if isinstance(event, Conform) and not facts.missing_files:
        problem = _critical_files_problem(folder, event, root)
        facts = replace(facts, critical_files_problem=problem)
    return facts


def record_context(
    folder: PlanFolder, state: PlanState | None, settings: Settings
) -> RecordContext:
    """Gather what the record-time guards need, from the settings, the state and the folder."""
    return RecordContext(
        ceiling=settings.max_autonomous_passes,
        gates_declared=state is not None and bool(state.approved_gates),
        blueprint_hash=folder.blueprint_hash(),
    )


def record(
    folder: PlanFolder,
    event: Event,
    settings: Settings,
    now: datetime,
    *,
    root: Path | None = None,
) -> Accepted | Refusal:
    """Append the event to the journal if the machine and the disk allow it.

    `root` is the project root, where git says what the branch changed: a `conform` needs it to
    have the files of its critical-files block checked against the branch. Raises `GitError` when
    that block lists files and the main branch or the merge base cannot be found.
    """
    if not folder.root.is_dir():
        message = f"{folder.root} is not a plan folder"
        raise PlanFolderError(message)
    state = load_state(folder)
    context = record_context(folder, state, settings)
    result = admit(state, event, context)
    if isinstance(result, Refusal):
        return result
    approved = None if state is None else state.approved_gates
    refusal = disk_guards(event, _disk_facts(folder, event, root), approved)
    if refusal is not None:
        return refusal
    append_line(folder.journal, JournalLine(timestamp(now), event))
    return result
