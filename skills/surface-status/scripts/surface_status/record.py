"""Record an event: replay, admit, check the disk, append (ADR 0012).

This is the only code that appends to a journal. Every step before the append only reads, so a
refusal leaves the journal byte for byte as it was, and an acceptance adds exactly one line.
"""

from dataclasses import replace
from datetime import UTC, datetime

from surface_status.events import Event, PlanAmended, PlanDrafted
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


def _disk_facts(folder: PlanFolder, event: Event) -> DiskFacts:
    facts = DiskFacts(
        missing_files=tuple(name for name in cited_files(event) if not folder.is_file(name)),
        overview_hash=folder.overview_hash(),
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
    return facts


def record_context(
    folder: PlanFolder, state: PlanState | None, settings: Settings
) -> RecordContext:
    """Gather what the record-time guards need, from the settings, the state and the folder."""
    return RecordContext(
        ceiling=settings.max_autonomous_passes,
        gates_declared=state is not None and bool(state.approved_gates),
        overview_hash=folder.overview_hash(),
    )


def record(
    folder: PlanFolder, event: Event, settings: Settings, now: datetime
) -> Accepted | Refusal:
    """Append the event to the journal if the machine and the disk allow it."""
    if not folder.root.is_dir():
        message = f"{folder.root} is not a plan folder"
        raise PlanFolderError(message)
    state = load_state(folder)
    context = record_context(folder, state, settings)
    result = admit(state, event, context)
    if isinstance(result, Refusal):
        return result
    approved = None if state is None else state.approved_gates
    refusal = disk_guards(event, _disk_facts(folder, event), approved)
    if refusal is not None:
        return refusal
    append_line(folder.journal, JournalLine(timestamp(now), event))
    return result
