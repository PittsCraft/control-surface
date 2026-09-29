"""Shared builders for the state tests: reference table, states, canonical journals, fixtures."""

from dataclasses import fields
from hashlib import sha256
from pathlib import Path
from typing import Any

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
from surface_status.guards import Accepted, RecordContext, Refusal, admit, fold
from surface_status.journal import read_events
from surface_status.machine import CheckSummary, Origin, PlanState, ReviewSummary, State

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "journals"


def digest(label: str) -> str:
    return "sha256:" + sha256(label.encode()).hexdigest()


OV1, OV2 = digest("overview 1"), digest("overview 2")
PL1, PL2 = digest("plan 1"), digest("plan 2")

S = State

# Specs section 6, "Transitions", transcribed a second time and independently of the package:
# event name, departure state (None: no journal), the arrival states the row allows.
EXPECTED: dict[str, dict[State | None, frozenset[State]]] = {
    "plan-opened": {None: frozenset({S.INTERVIEW})},
    "interview-closed": {S.INTERVIEW: frozenset({S.DRAFTING})},
    "check-done": {S.DRAFTING: frozenset({S.DRAFTING})},
    "plan-drafted": {S.DRAFTING: frozenset({S.AWAITING_APPROVAL})},
    "amendment-received": {
        S.AWAITING_APPROVAL: frozenset({S.DRAFTING}),
        S.BLOCKED: frozenset({S.DRAFTING}),
    },
    "plan-approved": {S.AWAITING_APPROVAL: frozenset({S.EXECUTING, S.REVIEWING})},
    "slice-done": {S.EXECUTING: frozenset({S.EXECUTING, S.REVIEWING})},
    "plan-amended": {
        S.EXECUTING: frozenset({S.EXECUTING, S.REVIEWING}),
        S.FIXING: frozenset({S.FIXING}),
    },
    "suspicion-dismissed": {S.EXECUTING: frozenset({S.EXECUTING})},
    "plan-change-proposed": {S.EXECUTING: frozenset({S.PLAN_CHANGE_PROPOSED})},
    "gates-run": {
        S.REVIEWING: frozenset({S.REVIEWING, S.FIXING}),
        S.FIXING: frozenset({S.FIXING}),
    },
    "review-done": {
        S.REVIEWING: frozenset({S.PLAN_CHANGE_PROPOSED, S.FIXING, S.REVIEWING}),
    },
    "fix-done": {S.FIXING: frozenset({S.REVIEWING})},
    "plan-change-accepted": {S.PLAN_CHANGE_PROPOSED: frozenset({S.DRAFTING})},
    "plan-change-refused": {S.PLAN_CHANGE_PROPOSED: frozenset({S.EXECUTING, S.FIXING})},
    "blocked": {
        S.DRAFTING: frozenset({S.BLOCKED}),
        S.EXECUTING: frozenset({S.BLOCKED}),
        S.REVIEWING: frozenset({S.BLOCKED}),
        S.FIXING: frozenset({S.BLOCKED}),
    },
    "resumed": {S.BLOCKED: frozenset({S.DRAFTING, S.EXECUTING, S.REVIEWING, S.FIXING})},
    "conform": {S.REVIEWING: frozenset({S.CONFORM})},
    "abandoned": {
        state: frozenset({S.ABANDONED})
        for state in (
            S.INTERVIEW,
            S.DRAFTING,
            S.AWAITING_APPROVAL,
            S.EXECUTING,
            S.REVIEWING,
            S.FIXING,
            S.PLAN_CHANGE_PROPOSED,
            S.BLOCKED,
        )
    },
}

CONTEXT = RecordContext(ceiling=3, gates_declared=True, overview_hash=OV1)

PROPOSAL = "plan-changes/01.md"


def state_in(state: State, **changes: Any) -> PlanState:  # noqa: ANN401 (overrides of any field)
    """Build a state that satisfies every guard of the events its table row allows."""
    base = PlanState(
        state=state,
        before_blocked=State.EXECUTING if state is State.BLOCKED else None,
        declared=frozenset({1, 2}),
        done=frozenset(),
        planning_passes=0,
        execution_passes=0,
        drafted_overview=OV1,
        drafted_plan=PL1,
        approved_overview=OV1,
        last_check=CheckSummary(rev=1, omissions=0, overview=OV1, plan=PL1),
        last_review=ReviewSummary(pass_=1, defects=0, deviations=0, breaks=0),
        gates=GateResult.PASS,
        proposal_origin=Origin.SLICE if state is State.PLAN_CHANGE_PROPOSED else None,
        pending_proposal=PROPOSAL if state is State.PLAN_CHANGE_PROPOSED else None,
        last_event=GatesRun(run=1, result=GateResult.PASS),
    )
    return PlanState(**{**{f.name: getattr(base, f.name) for f in fields(base)}, **changes})


def valid_event(name: str) -> Event:
    """Build an event of that name that the guards accept from `state_in(...)`."""
    events: dict[str, Event] = {
        "plan-opened": PlanOpened(slug="feature"),
        "interview-closed": InterviewClosed(),
        "check-done": CheckDone(
            rev=1, report="checks/rev-01-01.md", omissions=0, overview=OV1, plan=PL1
        ),
        "plan-drafted": PlanDrafted(rev=1, overview=OV1, plan=PL1, slices=(1, 2)),
        "amendment-received": AmendmentReceived(),
        "plan-approved": PlanApproved(rev=1, overview=OV1),
        "slice-done": SliceDone(slice_=1, gates="lint"),
        "plan-amended": PlanAmended(slice_=1, why="renamed", plan=PL2, slices=(1, 2)),
        "suspicion-dismissed": SuspicionDismissed(slice_=1, report="reviews/suspicion-01.md"),
        "plan-change-proposed": PlanChangeProposed(proposal=PROPOSAL, slice_=1),
        "gates-run": GatesRun(run=2, result=GateResult.PASS),
        "review-done": ReviewDone(
            pass_=2, report="reviews/pass-02.md", defects=0, deviations=0, breaks=0
        ),
        "fix-done": FixDone(pass_=1),
        "plan-change-accepted": PlanChangeAccepted(proposal=PROPOSAL),
        "plan-change-refused": PlanChangeRefused(proposal=PROPOSAL, why="not wanted"),
        "blocked": Blocked(why="does not converge"),
        "resumed": Resumed(),
        "conform": Conform(conformity="conformity.md", overview=OV1),
        "abandoned": Abandoned(why="changed my mind"),
    }
    return events[name]


def journal(*events: Event) -> list[Event]:
    return list(events)


def must_accept(
    prev: PlanState | None, event: Event, context: RecordContext | None = CONTEXT
) -> PlanState:
    result = admit(prev, event, context)
    assert isinstance(result, Accepted), result
    return result.state


def must_refuse(
    prev: PlanState | None, event: Event, context: RecordContext | None = CONTEXT
) -> Refusal:
    result = admit(prev, event, context)
    assert isinstance(result, Refusal), result
    return result


# Canonical journals, each ending in the state its name gives. Slices 1 and 2 are declared.
OPENED = journal(PlanOpened(slug="feature"))
DRAFTING = [*OPENED, InterviewClosed()]
CHECKED = [
    *DRAFTING,
    CheckDone(rev=1, report="checks/rev-01-01.md", omissions=0, overview=OV1, plan=PL1),
]
AWAITING = [*CHECKED, PlanDrafted(rev=1, overview=OV1, plan=PL1, slices=(1, 2))]
EXECUTING = [*AWAITING, PlanApproved(rev=1, overview=OV1)]
REVIEWING = [*EXECUTING, SliceDone(slice_=1, gates="lint"), SliceDone(slice_=2, gates="lint")]
GATED = [*REVIEWING, GatesRun(run=1, result=GateResult.PASS)]
FIXING = [
    *GATED,
    ReviewDone(pass_=1, report="reviews/pass-01.md", defects=1, deviations=0, breaks=0),
]


def replay(events: list[Event]) -> PlanState:
    state = fold(events)
    assert state is not None
    return state


def load_journal(path: Path) -> list[Event]:
    """Read a fixture with the strict codec of the journal."""
    return read_events(path)
