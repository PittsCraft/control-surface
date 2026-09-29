"""The arrival states that depend on the journal: slices remaining, gates, review, origin."""

import pytest
from state_support import (
    AWAITING,
    CONTEXT,
    EXECUTING,
    FIXING,
    OV1,
    PL2,
    PROPOSAL,
    REVIEWING,
    must_accept,
    replay,
    state_in,
)

from surface_status.events import (
    Blocked,
    Event,
    GateResult,
    GatesRun,
    PlanAmended,
    PlanApproved,
    PlanChangeProposed,
    PlanChangeRefused,
    Resumed,
    ReviewDone,
    SliceDone,
)
from surface_status.machine import Origin, State


def test_approval_goes_to_executing_when_slices_remain() -> None:
    assert replay([*AWAITING, PlanApproved(rev=1, overview=OV1)]).state is State.EXECUTING


def test_approval_goes_to_reviewing_when_every_declared_slice_is_done() -> None:
    prev = state_in(State.AWAITING_APPROVAL, declared=frozenset({1, 2}), done=frozenset({1, 2}))
    assert must_accept(prev, PlanApproved(rev=2, overview=OV1)).state is State.REVIEWING


def test_approval_of_a_plan_without_slices_goes_to_reviewing() -> None:
    prev = state_in(State.AWAITING_APPROVAL, declared=frozenset())
    assert must_accept(prev, PlanApproved(rev=1, overview=OV1)).state is State.REVIEWING


def test_the_last_slice_moves_to_reviewing_and_the_others_do_not() -> None:
    first = replay([*EXECUTING, SliceDone(slice_=1, gates="lint")])
    assert first.state is State.EXECUTING
    assert first.remaining == (2,)
    last = replay(
        [*EXECUTING, SliceDone(slice_=2, gates="lint"), SliceDone(slice_=1, gates="lint")]
    )
    assert last.state is State.REVIEWING
    assert last.remaining == ()


@pytest.mark.parametrize(
    ("slices", "arrival"),
    [((1, 2), State.EXECUTING), ((1, 2, 3), State.EXECUTING), ((1,), State.REVIEWING)],
)
def test_an_amendment_in_execution_recomputes_the_slices_left(
    slices: tuple[int, ...], arrival: State
) -> None:
    prev = state_in(State.EXECUTING, declared=frozenset({1, 2}), done=frozenset({1}))
    event = PlanAmended(slice_=2, why="reshaped", plan=PL2, slices=slices)
    assert must_accept(prev, event).state is arrival


def test_an_amendment_in_a_fix_keeps_fixing() -> None:
    assert (
        replay([*FIXING, PlanAmended(slice_=1, why="x", plan=PL2, slices=(1, 2))]).state
        is State.FIXING
    )


@pytest.mark.parametrize("departure", [State.REVIEWING, State.FIXING])
def test_green_gates_leave_the_state_unchanged(departure: State) -> None:
    assert (
        must_accept(state_in(departure), GatesRun(run=3, result=GateResult.PASS)).state is departure
    )


@pytest.mark.parametrize("departure", [State.REVIEWING, State.FIXING])
@pytest.mark.parametrize("result", [GateResult.FAIL, GateResult.TIMEOUT])
def test_failed_gates_and_timeouts_lead_to_fixing(departure: State, result: GateResult) -> None:
    assert must_accept(state_in(departure), GatesRun(run=3, result=result)).state is State.FIXING


@pytest.mark.parametrize(
    ("defects", "deviations", "breaks", "arrival"),
    [
        (0, 0, 0, State.REVIEWING),
        (1, 0, 0, State.FIXING),
        (0, 1, 0, State.FIXING),
        (2, 3, 0, State.FIXING),
        (0, 0, 1, State.PLAN_CHANGE_PROPOSED),
        (4, 2, 1, State.PLAN_CHANGE_PROPOSED),
    ],
)
def test_a_review_leads_where_its_worst_finding_says(
    defects: int, deviations: int, breaks: int, arrival: State
) -> None:
    event = ReviewDone(
        pass_=1,
        report="reviews/pass-01.md",
        defects=defects,
        deviations=deviations,
        breaks=breaks,
        proposal=PROPOSAL if breaks else None,
    )
    assert must_accept(state_in(State.REVIEWING), event).state is arrival


def test_a_refused_change_returns_to_executing_when_it_came_from_a_slice() -> None:
    proposed = replay([*EXECUTING, PlanChangeProposed(proposal=PROPOSAL, slice_=1)])
    assert proposed.proposal_origin is Origin.SLICE
    refused = must_accept(proposed, PlanChangeRefused(proposal=PROPOSAL, why="no"))
    assert refused.state is State.EXECUTING
    assert refused.proposal_origin is None


def test_a_refused_change_returns_to_fixing_when_a_review_raised_it() -> None:
    review = ReviewDone(
        pass_=1, report="reviews/pass-01.md", defects=0, deviations=0, breaks=1, proposal=PROPOSAL
    )
    proposed = replay([*REVIEWING, GatesRun(run=1, result=GateResult.PASS), review])
    assert proposed.state is State.PLAN_CHANGE_PROPOSED
    assert proposed.proposal_origin is Origin.REVIEW
    assert proposed.pending_proposal == PROPOSAL
    refused = must_accept(proposed, PlanChangeRefused(proposal=PROPOSAL, why="no"))
    assert refused.state is State.FIXING
    assert refused.pending_proposal is None


@pytest.mark.parametrize("before", [State.DRAFTING, State.EXECUTING, State.REVIEWING, State.FIXING])
def test_resumed_goes_back_to_the_state_that_preceded_blocked(before: State) -> None:
    blocked = must_accept(state_in(before), Blocked(why="does not converge"))
    assert blocked.state is State.BLOCKED
    assert blocked.before_blocked is before
    resumed = must_accept(blocked, Resumed())
    assert resumed.state is before
    assert resumed.before_blocked is None


def test_context_does_not_change_the_arrival() -> None:
    events: list[Event] = [SliceDone(slice_=1, gates="lint")]
    prev = state_in(State.EXECUTING)
    assert must_accept(prev, events[0], None) == must_accept(prev, events[0], CONTEXT)
