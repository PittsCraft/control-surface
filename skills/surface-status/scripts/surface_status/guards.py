"""Whether an event may be recorded now, and the checked replay built on it.

Two families of guards (ADR 0011):

- Journal-only guards need the state and the event, nothing else. They are checked when a journal
  is replayed and when an event is recorded, so a hand edited journal cannot slip through replay.
- Record-time guards need a fact that lives outside the journal or is worked out before the
  record: the ceiling from the settings, whether the approved plan names gates, the current hash
  of `blueprint.md`. `RecordContext` carries them in as plain values, so this module still reads
  no file. Replay has no context and skips them, since a setting that changed since the event was
  recorded must not make the old journal invalid.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
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
from surface_status.machine import TRANSITIONS, PlanState, State, apply, sends_work_back


class RefusalCode(StrEnum):
    TRANSITION = "transition"  # the pair (event, state) is not in the table
    CROSS_CHECK = "cross-check"
    DRAFT_HASH = "draft-hash"
    BLUEPRINT_CHANGED = "blueprint-changed"
    SLICE = "slice"
    SLICE_LIST = "slice-list"
    PROPOSAL = "proposal"
    GATES = "gates"
    CONFORMITY = "conformity"
    CEILING = "ceiling"
    FILE_MISSING = "file-missing"
    HASH_STALE = "hash-stale"
    SLICES_STALE = "slices-stale"
    SUSPICION = "suspicion"  # a suspected break waits for a reviewer's judgment
    GATE_LIST = "gate-list"  # the gates block of `plan.md` is missing, malformed, or changed
    # The critical-files block of `conformity.md` is malformed, or lists a file the branch did not
    # change.
    CRITICAL_FILES = "critical-files"


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
    gates_declared: bool  # the approved revision of the plan names at least one gate command
    blueprint_hash: str | None  # current hash of `blueprint.md`, None when the file is missing


@dataclass(frozen=True, slots=True)
class DiskFacts:
    """What the caller read from the plan folder for one event, as plain values.

    For a `conformant`, the caller also asked git what the branch changed.

    `None` means the file is missing or unreadable, which `missing_files` already reports.
    """

    missing_files: tuple[str, ...]  # cited files that are not regular files of the folder
    blueprint_hash: str | None
    plan_hash: str | None
    slices: tuple[int, ...] | None  # markers of `plan.md`, read only for events that carry slices
    slices_problem: str | None = None  # why the markers could not be read, if they could not
    gates: tuple[str, ...] | None = None  # the gates block of `plan.md`, for the same events
    gates_problem: str | None = None  # why the gates block could not be read, if it could not
    # Why the critical-files block of the `conformity.md` a `conformant` cites cannot be taken.
    critical_files_problem: str | None = None


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
    if check.blueprint != event.blueprint or check.plan != event.plan:
        return _refuse(
            RefusalCode.CROSS_CHECK,
            "the last cross-check did not cover the current hashes of the blueprint and the plan",
        )
    return None


def _check_approved(prev: PlanState, event: PlanApproved) -> Refusal | None:
    if event.blueprint != prev.drafted_blueprint:
        return _refuse(
            RefusalCode.DRAFT_HASH,
            "the blueprint differs from the one of the last plan-drafted",
        )
    return None


def _check_unjudged(prev: PlanState) -> Refusal | None:
    """Refuse to carry on past a suspected break that no reviewer has judged."""
    if prev.suspicion is None:
        return None
    return _refuse(
        RefusalCode.SUSPICION,
        f"a break is suspected during slice {prev.suspicion.slice_}: a reviewer judges it first",
    )


def _check_judged(
    prev: PlanState, event: SuspicionDismissed | PlanChangeProposed
) -> Refusal | None:
    """Match a judgment to the suspicion that is pending, when one is.

    A journal written before `break-suspected` existed judges a suspicion it never recorded, so
    a judgment with no pending suspicion stays accepted.
    """
    if prev.suspicion is None or prev.suspicion.slice_ == event.slice_:
        return None
    return _refuse(
        RefusalCode.SUSPICION,
        f"the break under judgment is suspected during slice {prev.suspicion.slice_}",
    )


def _check_slice(prev: PlanState, event: SliceDone | BreakSuspected) -> Refusal | None:
    unjudged = _check_unjudged(prev)
    if unjudged is not None:
        return unjudged
    if event.slice_ not in prev.declared:
        return _refuse(RefusalCode.SLICE, f"slice {event.slice_} is not in the declared list")
    if event.slice_ in prev.done:
        return _refuse(RefusalCode.SLICE, f"slice {event.slice_} is already done")
    return None


def _check_amended(prev: PlanState, event: PlanAmended) -> Refusal | None:
    unjudged = _check_unjudged(prev)
    if unjudged is not None:
        return unjudged
    if prev.state is State.FIXING and frozenset(event.slices) != prev.declared:
        return _refuse(RefusalCode.SLICE_LIST, "a fix cannot change the list of slices")
    return None


def _check_review(event: ReviewDone) -> Refusal | None:
    if event.breaks > 0 and event.proposal is None:
        return _refuse(RefusalCode.PROPOSAL, "a break needs a plan change proposal")
    return None


def _check_conformant(prev: PlanState, event: Conformant) -> Refusal | None:
    if event.blueprint != prev.approved_blueprint:
        return _refuse(
            RefusalCode.BLUEPRINT_CHANGED,
            "the blueprint differs from the one of the last plan-approved",
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
        case SliceDone() | BreakSuspected():
            return _check_slice(prev, event)
        case PlanAmended():
            return _check_amended(prev, event)
        case SuspicionDismissed() | PlanChangeProposed():
            return _check_judged(prev, event)
        case ReviewDone():
            return _check_review(event)
        case Conformant():
            return _check_conformant(prev, event)
        case (
            PlanOpened()
            | InterviewClosed()
            | CheckDone()
            | AmendmentReceived()
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


def _check_ceiling(prev: PlanState, event: Event, context: RecordContext) -> Refusal | None:
    """Refuse a pass the loop may no longer take on its own.

    A pass sends work back to an agent: in planning a check with omissions, which sends the
    blueprint or the plan back for rework; in execution what `sends_work_back` names. Both loops
    send work back `ceiling` times; the pass that would send it once more is still recorded,
    since it holds what does not converge, and hands back; none after it. So a ceiling of 3 gives
    three reworks in planning and three fixes in execution, a fixer whose own gate run fails
    being one pass and the fixer sent after it the next.
    """
    if isinstance(event, CheckDone) and event.omissions > 0:
        passes = prev.planning_passes
    elif sends_work_back(event):
        passes = prev.execution_passes
    else:
        return None
    if passes > context.ceiling:
        return _refuse(
            RefusalCode.CEILING,
            f"{passes} autonomous passes went past the ceiling of {context.ceiling}",
        )
    return None


def _check_blueprint_frozen(
    prev: PlanState, event: Event, context: RecordContext
) -> Refusal | None:
    if not isinstance(event, SliceDone | PlanAmended | FixDone | Conformant):
        return None
    if context.blueprint_hash is None or context.blueprint_hash != prev.approved_blueprint:
        return _refuse(
            RefusalCode.BLUEPRINT_CHANGED,
            "the blueprint differs from the one of the last plan-approved",
        )
    return None


def _check_gates(prev: PlanState, event: Event, context: RecordContext) -> Refusal | None:
    if not context.gates_declared:
        return None  # the approved plan names no gate, so nothing cites a gate run
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
        _check_blueprint_frozen(prev, event, context)
        or _check_ceiling(prev, event, context)
        or _check_gates(prev, event, context)
    )


def _stale(what: str, recorded: str, current: str | None) -> Refusal | None:
    if current is None or recorded == current:
        return None
    return _refuse(RefusalCode.HASH_STALE, f"the {what} hash is not the current one of the file")


def _check_gate_list(
    event: Event, facts: DiskFacts, approved: tuple[str, ...] | None
) -> Refusal | None:
    """Refuse a draft without its gates, and an amendment that changes the approved ones."""
    if not isinstance(event, PlanDrafted | PlanAmended):
        return None
    if facts.gates_problem is not None:
        return _refuse(RefusalCode.GATE_LIST, facts.gates_problem)
    if isinstance(event, PlanDrafted):
        if facts.gates is None:
            return _refuse(
                RefusalCode.GATE_LIST,
                "plan.md has no gates block: name the commands that check the project,"
                " or leave the block empty when it has none",
            )
        if event.gates != facts.gates:
            return _refuse(RefusalCode.GATE_LIST, "the gates are not those of plan.md")
    elif approved is not None and facts.gates != approved:
        return _refuse(
            RefusalCode.GATE_LIST,
            "the gates block differs from the approved one: only a new revision changes the gates",
        )
    return None


def _check_critical_files(event: Event, facts: DiskFacts) -> Refusal | None:
    """Refuse a conformity whose list of code to read cannot be shown as the reviewer wrote it."""
    if not isinstance(event, Conformant) or facts.critical_files_problem is None:
        return None
    return _refuse(RefusalCode.CRITICAL_FILES, facts.critical_files_problem)


def disk_guards(
    event: Event, facts: DiskFacts, approved_gates: tuple[str, ...] | None = None
) -> Refusal | None:
    """Apply the guards that need the plan folder: cited files exist, derived values are current.

    The script computes hashes, slice lists and gates itself (ADR 0012); this refuses an event
    that carries a value read before the file changed. `approved_gates` are those of the approved
    revision, which a `plan-amended` must leave as they are. A `conformant` is refused when the
    critical-files block of the `conformity.md` it cites is malformed or lists a file the branch
    did not change: the description would show the developer a wrong list of code to read.
    """
    if facts.missing_files:
        return _refuse(
            RefusalCode.FILE_MISSING, "cited file missing: " + ", ".join(facts.missing_files)
        )
    if isinstance(event, CheckDone | PlanDrafted | PlanApproved | Conformant):
        stale = _stale("blueprint", event.blueprint, facts.blueprint_hash)
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
    return _check_critical_files(event, facts) or _check_gate_list(event, facts, approved_gates)


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
