"""Whether an event may be recorded now, and the checked replay built on it.

Two families of guards (ADR 0011):

- Journal-only guards need the state and the event, nothing else. They are checked when a journal
  is replayed and when an event is recorded, so a hand edited journal cannot slip through replay.
- Record-time guards need a fact that lives outside the journal: the ceiling and the gate command
  from the settings, the current hash of `overview.md`. `RecordContext` carries them in as plain
  values, so this module still reads no file. Replay has no context and skips them, since a
  setting that changed since the event was recorded must not make the old journal invalid.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from surface_status.events import (
    Abandoned,
    AmendmentReceived,
    Blocked,
    CheckDone,
    Conform,
    Event,
    FixDone,
    GateResult,
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
from surface_status.machine import TRANSITIONS, PlanState, State, apply


class RefusalCode(StrEnum):
    TRANSITION = "transition"  # the pair (event, state) is not in the table
    CROSS_CHECK = "cross-check"
    DRAFT_HASH = "draft-hash"
    OVERVIEW_CHANGED = "overview-changed"
    SLICE = "slice"
    SLICE_LIST = "slice-list"
    PROPOSAL = "proposal"
    GATES = "gates"
    CONFORMITY = "conformity"
    CEILING = "ceiling"
    FILE_MISSING = "file-missing"
    HASH_STALE = "hash-stale"
    SLICES_STALE = "slices-stale"


@dataclass(frozen=True, slots=True)
class Refusal:
    code: RefusalCode
    reason: str


@dataclass(frozen=True, slots=True)
class Accepted:
    state: PlanState


@dataclass(frozen=True, slots=True)
class RecordContext:
    """What the caller read outside the journal before recording."""

    ceiling: int  # `max_autonomous_passes`
    gates_declared: bool  # the project declares a gate command
    overview_hash: str | None  # current hash of `overview.md`, None when the file is missing


@dataclass(frozen=True, slots=True)
class DiskFacts:
    """What the caller read from the plan folder for one event, as plain values.

    `None` means the file is missing or unreadable, which `missing_files` already reports.
    """

    missing_files: tuple[str, ...]  # cited files that are not regular files of the folder
    overview_hash: str | None
    plan_hash: str | None
    slices: tuple[int, ...] | None  # markers of `plan.md`, read only for events that carry slices
    slices_problem: str | None = None  # why the markers could not be read, if they could not


class InvalidJournalError(Exception):
    def __init__(self, index: int, event: Event, refusal: Refusal) -> None:
        super().__init__(
            f"line {index + 1}: {event.name} refused ({refusal.code}): {refusal.reason}"
        )
        self.index = index
        self.event = event
        self.refusal = refusal


def _refuse(code: RefusalCode, reason: str) -> Refusal:
    return Refusal(code, reason)


def _check_drafted(prev: PlanState, event: PlanDrafted) -> Refusal | None:
    check = prev.last_check
    if check is None or check.rev != event.rev:
        return _refuse(
            RefusalCode.CROSS_CHECK, f"no cross-check was recorded for revision {event.rev}"
        )
    if check.omissions > 0:
        return _refuse(
            RefusalCode.CROSS_CHECK,
            f"the last cross-check of revision {event.rev} counts {check.omissions} omissions",
        )
    if check.overview != event.overview or check.plan != event.plan:
        return _refuse(
            RefusalCode.CROSS_CHECK,
            "the last cross-check did not cover the current hashes of the overview and the plan",
        )
    return None


def _check_approved(prev: PlanState, event: PlanApproved) -> Refusal | None:
    if event.overview != prev.drafted_overview:
        return _refuse(
            RefusalCode.DRAFT_HASH,
            "the overview differs from the one of the last plan-drafted",
        )
    return None


def _check_slice(prev: PlanState, event: SliceDone) -> Refusal | None:
    if event.slice_ not in prev.declared:
        return _refuse(RefusalCode.SLICE, f"slice {event.slice_} is not in the declared list")
    if event.slice_ in prev.done:
        return _refuse(RefusalCode.SLICE, f"slice {event.slice_} is already done")
    return None


def _check_amended(prev: PlanState, event: PlanAmended) -> Refusal | None:
    if prev.state is State.FIXING and frozenset(event.slices) != prev.declared:
        return _refuse(RefusalCode.SLICE_LIST, "a fix cannot change the list of slices")
    return None


def _check_review(event: ReviewDone) -> Refusal | None:
    if event.breaks > 0 and event.proposal is None:
        return _refuse(RefusalCode.PROPOSAL, "a break needs a plan change proposal")
    return None


def _check_conform(prev: PlanState, event: Conform) -> Refusal | None:
    if event.overview != prev.approved_overview:
        return _refuse(
            RefusalCode.OVERVIEW_CHANGED,
            "the overview differs from the one of the last plan-approved",
        )
    review = prev.last_review
    if review is None:
        return _refuse(RefusalCode.CONFORMITY, "no review since the last change of the work")
    if not review.clean:
        return _refuse(
            RefusalCode.CONFORMITY,
            f"the last review counts {review.defects} defects, {review.deviations} deviations"
            f" and {review.breaks} breaks",
        )
    return None


def journal_guards(prev: PlanState | None, event: Event) -> Refusal | None:  # noqa: PLR0911 (one arm per event)
    """Apply the guards that need the state and the event only."""
    if prev is None:
        return None
    match event:
        case PlanDrafted():
            return _check_drafted(prev, event)
        case PlanApproved():
            return _check_approved(prev, event)
        case SliceDone():
            return _check_slice(prev, event)
        case PlanAmended():
            return _check_amended(prev, event)
        case ReviewDone():
            return _check_review(event)
        case Conform():
            return _check_conform(prev, event)
        case (
            PlanOpened()
            | InterviewClosed()
            | CheckDone()
            | AmendmentReceived()
            | SuspicionDismissed()
            | PlanChangeProposed()
            | GatesRun()
            | FixDone()
            | PlanChangeAccepted()
            | PlanChangeRefused()
            | Blocked()
            | Resumed()
            | Abandoned()
        ):
            return None
        case _:
            assert_never(event)


def _pass_count(prev: PlanState, event: Event) -> int | None:
    """Return the counter an event would raise if it is a loop pass, None if it is not one."""
    match event:
        case CheckDone() if event.omissions > 0:
            return prev.planning_passes
        case ReviewDone() | SuspicionDismissed():
            return prev.execution_passes
        case GatesRun() if event.result is not GateResult.PASS:
            return prev.execution_passes
        case _:
            return None


def _check_ceiling(prev: PlanState, event: Event, context: RecordContext) -> Refusal | None:
    passes = _pass_count(prev, event)
    if passes is not None and passes >= context.ceiling:
        return _refuse(
            RefusalCode.CEILING,
            f"{passes} autonomous passes reached the ceiling of {context.ceiling}",
        )
    return None


def _check_overview_frozen(prev: PlanState, event: Event, context: RecordContext) -> Refusal | None:
    if not isinstance(event, SliceDone | PlanAmended | FixDone | Conform):
        return None
    if context.overview_hash is None or context.overview_hash != prev.approved_overview:
        return _refuse(
            RefusalCode.OVERVIEW_CHANGED,
            "the overview differs from the one of the last plan-approved",
        )
    return None


def _check_gates(prev: PlanState, event: Event, context: RecordContext) -> Refusal | None:
    if not context.gates_declared:
        return None  # no gate command, so nothing cites a gate run
    if isinstance(event, ReviewDone) and prev.gates is not GateResult.PASS:
        return _refuse(
            RefusalCode.GATES, "no green gate run since the last slice or the last review"
        )
    if isinstance(event, FixDone) and not (
        isinstance(prev.last_event, GatesRun) and prev.last_event.result is GateResult.PASS
    ):
        return _refuse(RefusalCode.GATES, "the previous event is not a green gate run")
    return None


def record_guards(prev: PlanState | None, event: Event, context: RecordContext) -> Refusal | None:
    """Apply the guards that need a fact from outside the journal."""
    if prev is None:
        return None
    return (
        _check_overview_frozen(prev, event, context)
        or _check_ceiling(prev, event, context)
        or _check_gates(prev, event, context)
    )


def _stale(what: str, recorded: str, current: str | None) -> Refusal | None:
    if current is None or recorded == current:
        return None
    return _refuse(RefusalCode.HASH_STALE, f"the {what} hash is not the current one of the file")


def disk_guards(event: Event, facts: DiskFacts) -> Refusal | None:
    """Apply the guards that need the plan folder: cited files exist, derived values are current.

    The script computes hashes and slice lists itself (ADR 0012); this refuses an event that
    carries a value read before the file changed.
    """
    if facts.missing_files:
        return _refuse(
            RefusalCode.FILE_MISSING, "cited file missing: " + ", ".join(facts.missing_files)
        )
    if isinstance(event, CheckDone | PlanDrafted | PlanApproved | Conform):
        stale = _stale("overview", event.overview, facts.overview_hash)
        if stale is not None:
            return stale
    if isinstance(event, CheckDone | PlanDrafted | PlanAmended):
        stale = _stale("plan", event.plan, facts.plan_hash)
        if stale is not None:
            return stale
    if isinstance(event, PlanDrafted | PlanAmended):
        if facts.slices_problem is not None:
            return _refuse(RefusalCode.SLICES_STALE, facts.slices_problem)
        if facts.slices is not None and event.slices != facts.slices:
            return _refuse(RefusalCode.SLICES_STALE, "the slices are not those of plan.md")
    return None


def admit(
    prev: PlanState | None, event: Event, context: RecordContext | None = None
) -> Accepted | Refusal:
    """Accept the event with the state it leads to, or refuse it with the reason.

    Without a context only the table and the journal-only guards apply, which is what replay does.
    """
    departure = None if prev is None else prev.state
    if departure not in TRANSITIONS[event.name]:
        return _refuse(RefusalCode.TRANSITION, f"{event.name} is not allowed from {departure}")
    refusal = journal_guards(prev, event)
    if refusal is None and context is not None:
        refusal = record_guards(prev, event, context)
    return refusal or Accepted(apply(prev, event))


def fold(events: Iterable[Event]) -> PlanState | None:
    """Replay a journal. None for an empty one; raises `InvalidJournalError` on an illegal line."""
    state: PlanState | None = None
    for index, event in enumerate(events):
        result = admit(state, event)
        if isinstance(result, Refusal):
            raise InvalidJournalError(index, event, result)
        state = result.state
    return state
