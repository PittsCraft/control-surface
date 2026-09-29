"""The states, the transition table and the pure step from one state to the next.

Nothing here reads a file, the clock or the environment: the state is a function of the events
alone (ADR 0011). Whether an event may be recorded is decided by `guards.admit`, which calls
`apply` once the table and the guards agree.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TypeAlias, assert_never

from surface_status.events import (
    Abandoned,
    AmendmentReceived,
    Blocked,
    BreakSuspected,
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


class State(StrEnum):
    INTERVIEW = "interview"
    DRAFTING = "drafting"
    AWAITING_APPROVAL = "awaiting-approval"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    FIXING = "fixing"
    PLAN_CHANGE_PROPOSED = "plan-change-proposed"
    BLOCKED = "blocked"
    CONFORM = "conform"
    ABANDONED = "abandoned"


TERMINAL = frozenset({State.CONFORM, State.ABANDONED})
NON_TERMINAL = tuple(state for state in State if state not in TERMINAL)


class Origin(StrEnum):
    """Where a pending plan change proposal came from."""

    SLICE = "slice"  # an executor suspected a break during a slice
    REVIEW = "review"  # a review found a break


class Rule(StrEnum):
    """An arrival state that depends on the journal, named after the condition it tests."""

    SLICES_REMAIN = "slices-remain"  # executing if slices remain, otherwise reviewing
    GATES = "gates"  # fixing if the gates failed, otherwise unchanged
    REVIEW = "review"  # proposal on a break, fixing on a defect or a deviation, else reviewing
    PROPOSAL_ORIGIN = "proposal-origin"  # executing if it came from a slice, otherwise fixing
    BEFORE_BLOCKED = "before-blocked"  # the state that preceded `blocked`


Arrival: TypeAlias = State | Rule

# Specs section 6, "Transitions": event name, then departure state, then arrival. The departure
# `None` is the journal that does not exist yet. A pair absent from this table is refused.
TRANSITIONS: Mapping[str, Mapping[State | None, Arrival]] = {
    "plan-opened": {None: State.INTERVIEW},
    "interview-closed": {State.INTERVIEW: State.DRAFTING},
    "check-done": {State.DRAFTING: State.DRAFTING},
    "plan-drafted": {State.DRAFTING: State.AWAITING_APPROVAL},
    "amendment-received": {
        State.AWAITING_APPROVAL: State.DRAFTING,
        State.BLOCKED: State.DRAFTING,
    },
    "plan-approved": {State.AWAITING_APPROVAL: Rule.SLICES_REMAIN},
    "slice-done": {State.EXECUTING: Rule.SLICES_REMAIN},
    "plan-amended": {State.EXECUTING: Rule.SLICES_REMAIN, State.FIXING: State.FIXING},
    "break-suspected": {State.EXECUTING: State.EXECUTING},
    "suspicion-dismissed": {State.EXECUTING: State.EXECUTING},
    "plan-change-proposed": {State.EXECUTING: State.PLAN_CHANGE_PROPOSED},
    "gates-run": {State.REVIEWING: Rule.GATES, State.FIXING: Rule.GATES},
    "review-done": {State.REVIEWING: Rule.REVIEW},
    "fix-done": {State.FIXING: State.REVIEWING},
    "plan-change-accepted": {State.PLAN_CHANGE_PROPOSED: State.DRAFTING},
    "plan-change-refused": {State.PLAN_CHANGE_PROPOSED: Rule.PROPOSAL_ORIGIN},
    "blocked": {
        State.DRAFTING: State.BLOCKED,
        State.EXECUTING: State.BLOCKED,
        State.REVIEWING: State.BLOCKED,
        State.FIXING: State.BLOCKED,
    },
    "resumed": {State.BLOCKED: Rule.BEFORE_BLOCKED},
    "conform": {State.REVIEWING: State.CONFORM},
    "abandoned": dict.fromkeys(NON_TERMINAL, State.ABANDONED),
}


@dataclass(frozen=True, slots=True)
class CheckSummary:
    """The last cross-check, as `plan-drafted` must find it."""

    rev: int
    omissions: int
    overview: str
    plan: str


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    pass_: int
    defects: int
    deviations: int
    breaks: int

    @property
    def clean(self) -> bool:
        return self.defects == 0 and self.deviations == 0 and self.breaks == 0


@dataclass(frozen=True, slots=True)
class Suspicion:
    """A break an executor suspected during a slice, that no reviewer has judged yet."""

    slice_: int
    why: str


@dataclass(frozen=True, slots=True)
class PlanState:
    state: State
    before_blocked: State | None  # set while `blocked`, to know where `resumed` goes back to
    declared: frozenset[int]  # slices of the last `plan-drafted` or `plan-amended`
    done: frozenset[int]
    planning_passes: int  # counted since the last act of the developer
    execution_passes: int
    drafted_overview: str | None
    drafted_plan: str | None
    drafted_gates: tuple[str, ...] | None  # gates of the last `plan-drafted`
    approved_overview: str | None  # hash of the last `plan-approved`
    approved_gates: tuple[str, ...] | None  # the drafted gates the last `plan-approved` took
    last_check: CheckSummary | None  # cleared when a new revision starts
    last_review: ReviewSummary | None  # cleared by any change of the work since that review
    gates: GateResult | None  # result of the last gate run, None once the work changed since
    proposal_origin: Origin | None
    pending_proposal: str | None
    suspicion: Suspicion | None  # kept until a reviewer judges it, or the plan is drawn again
    last_event: Event

    @property
    def remaining(self) -> tuple[int, ...]:
        return tuple(sorted(self.declared - self.done))

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL


def _opened(event: PlanOpened) -> PlanState:
    return PlanState(
        state=State.INTERVIEW,
        before_blocked=None,
        declared=frozenset(),
        done=frozenset(),
        planning_passes=0,
        execution_passes=0,
        drafted_overview=None,
        drafted_plan=None,
        drafted_gates=None,
        approved_overview=None,
        approved_gates=None,
        last_check=None,
        last_review=None,
        gates=None,
        proposal_origin=None,
        pending_proposal=None,
        suspicion=None,
        last_event=event,
    )


def _record(prev: PlanState, event: Event) -> PlanState:  # noqa: C901, PLR0911, PLR0912
    """Return the facts an event changes, before the arrival state is resolved."""
    match event:
        case PlanOpened():
            message = "plan-opened only starts a journal"
            raise LookupError(message)
        case InterviewClosed():
            return replace(prev, planning_passes=0)
        case CheckDone():
            check = CheckSummary(event.rev, event.omissions, event.overview, event.plan)
            passes = prev.planning_passes + (1 if event.omissions > 0 else 0)
            return replace(prev, last_check=check, planning_passes=passes)
        case PlanDrafted():
            return replace(
                prev,
                drafted_overview=event.overview,
                drafted_plan=event.plan,
                drafted_gates=event.gates,
                declared=frozenset(event.slices),
            )
        case AmendmentReceived():
            return replace(
                prev,
                planning_passes=0,
                last_check=None,
                last_review=None,
                gates=None,
                suspicion=None,
            )
        case PlanApproved():
            return replace(
                prev,
                approved_overview=event.overview,
                approved_gates=prev.drafted_gates,
                execution_passes=0,
                last_review=None,
                gates=None,
            )
        case SliceDone():
            return replace(prev, done=prev.done | {event.slice_}, last_review=None, gates=None)
        case PlanAmended():
            return replace(prev, declared=frozenset(event.slices))
        case BreakSuspected():
            return replace(prev, suspicion=Suspicion(event.slice_, event.why))
        case SuspicionDismissed():
            return replace(prev, execution_passes=prev.execution_passes + 1, suspicion=None)
        case PlanChangeProposed():
            return replace(
                prev,
                proposal_origin=Origin.SLICE,
                pending_proposal=event.proposal,
                suspicion=None,
            )
        case GatesRun():
            failed = event.result is not GateResult.PASS
            return replace(
                prev,
                gates=event.result,
                execution_passes=prev.execution_passes + (1 if failed else 0),
            )
        case ReviewDone():
            review = ReviewSummary(event.pass_, event.defects, event.deviations, event.breaks)
            broke = event.breaks > 0
            return replace(
                prev,
                last_review=review,
                gates=None,
                execution_passes=prev.execution_passes + 1,
                proposal_origin=Origin.REVIEW if broke else prev.proposal_origin,
                pending_proposal=event.proposal if broke else prev.pending_proposal,
            )
        case FixDone():
            return replace(prev, last_review=None)
        case PlanChangeAccepted():
            return replace(
                prev,
                planning_passes=0,
                last_check=None,
                last_review=None,
                gates=None,
                proposal_origin=None,
                pending_proposal=None,
            )
        case PlanChangeRefused():
            return replace(prev, execution_passes=0, proposal_origin=None, pending_proposal=None)
        case Blocked():
            return replace(prev, before_blocked=prev.state)
        case Resumed():
            return replace(prev, planning_passes=0, execution_passes=0)
        case Conform() | Abandoned():
            return prev
        case _:
            assert_never(event)


def _resolve(  # noqa: PLR0911 (one arm per rule)
    arrival: Arrival, facts: PlanState, prev: PlanState, event: Event
) -> State:
    """Return the arrival state, from the facts once `event` is recorded."""
    match arrival:
        case State():
            return arrival
        case Rule.SLICES_REMAIN:
            return State.EXECUTING if facts.remaining else State.REVIEWING
        case Rule.GATES:
            passed = isinstance(event, GatesRun) and event.result is GateResult.PASS
            return prev.state if passed else State.FIXING
        case Rule.REVIEW:
            review = facts.last_review
            if review is None or review.clean:
                return State.REVIEWING
            return State.PLAN_CHANGE_PROPOSED if review.breaks > 0 else State.FIXING
        case Rule.PROPOSAL_ORIGIN:
            return State.EXECUTING if prev.proposal_origin is Origin.SLICE else State.FIXING
        case Rule.BEFORE_BLOCKED:
            if prev.before_blocked is None:
                message = "a blocked state always records the state that preceded it"
                raise LookupError(message)
            return prev.before_blocked
        case _:
            assert_never(arrival)


def apply(prev: PlanState | None, event: Event) -> PlanState:
    """Step from `prev` to the next state; the caller has checked the table and the guards.

    Raises `LookupError` for a pair the table does not hold, which the guards keep out of reach.
    """
    departure = None if prev is None else prev.state
    arrival = TRANSITIONS[event.name].get(departure)
    if arrival is None:
        message = f"{event.name} is not a transition from {departure}"
        raise LookupError(message)
    if prev is None:
        if not isinstance(event, PlanOpened):
            message = "only plan-opened starts a journal"
            raise LookupError(message)
        return _opened(event)
    facts = _record(prev, event)
    target = _resolve(arrival, facts, prev, event)
    return replace(
        facts,
        state=target,
        before_blocked=None if target is not State.BLOCKED else facts.before_blocked,
        last_event=event,
    )
