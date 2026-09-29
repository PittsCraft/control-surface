"""The pass counters, reset by each act of the developer, and no pass beyond the ceiling."""

import pytest
from state_support import (
    CHECKED,
    DRAFTING,
    EXECUTING,
    FIXING,
    GATED,
    OV1,
    PL1,
    PROPOSAL,
    REVIEWING,
    must_accept,
    must_refuse,
    replay,
    state_in,
)

from surface_status.events import (
    AmendmentReceived,
    Blocked,
    CheckDone,
    Conform,
    Event,
    GateResult,
    GatesRun,
    InterviewClosed,
    PlanApproved,
    PlanChangeAccepted,
    PlanChangeProposed,
    PlanChangeRefused,
    PlanDrafted,
    Resumed,
    ReviewDone,
    SuspicionDismissed,
)
from surface_status.guards import RecordContext, RefusalCode
from surface_status.machine import PlanState, State


def context(ceiling: int) -> RecordContext:
    return RecordContext(ceiling=ceiling, gates_declared=True, overview_hash=OV1)


def check(omissions: int) -> CheckDone:
    return CheckDone(rev=1, report="r", omissions=omissions, overview=OV1, plan=PL1)


def review(*, defects: int = 0) -> ReviewDone:
    return ReviewDone(pass_=1, report="r", defects=defects, deviations=0, breaks=0)


class TestPlanning:
    def test_only_a_check_with_omissions_counts(self) -> None:
        state = replay(DRAFTING)
        state = must_accept(state, check(0))
        assert state.planning_passes == 0
        state = must_accept(state, check(3))
        assert state.planning_passes == 1
        state = must_accept(state, check(1))
        assert state.planning_passes == 2

    @pytest.mark.parametrize("resetting", ["interview-closed", "amendment", "accepted", "resumed"])
    def test_restarts_from_zero_at_each_act_of_the_developer(self, resetting: str) -> None:
        cases: dict[str, tuple[State, Event]] = {
            "interview-closed": (State.INTERVIEW, InterviewClosed()),
            "amendment": (State.AWAITING_APPROVAL, AmendmentReceived()),
            "accepted": (State.PLAN_CHANGE_PROPOSED, PlanChangeAccepted(proposal=PROPOSAL)),
            "resumed": (State.BLOCKED, Resumed()),
        }
        state, event = cases[resetting]
        before = state_in(state, planning_passes=2, execution_passes=2)
        if state is State.BLOCKED:
            before = state_in(State.BLOCKED, planning_passes=2, before_blocked=State.DRAFTING)
        assert must_accept(before, event).planning_passes == 0

    def test_is_not_restarted_by_a_draft_nor_by_the_execution_events(self) -> None:
        state = must_accept(replay(DRAFTING), check(1))
        state = must_accept(state, check(0))
        drafted = must_accept(state, PlanDrafted(rev=1, overview=OV1, plan=PL1, slices=(1, 2)))
        assert drafted.planning_passes == 1

    def test_the_execution_events_leave_it_alone(self) -> None:
        state = state_in(State.REVIEWING, planning_passes=2)
        assert must_accept(state, review(defects=1)).planning_passes == 2


class TestExecution:
    def test_counts_reviews_dismissed_suspicions_and_failed_gates(self) -> None:
        state = state_in(State.EXECUTING)
        state = must_accept(state, SuspicionDismissed(slice_=1, report="r"))
        assert state.execution_passes == 1
        state = state_in(State.REVIEWING)
        assert must_accept(state, review()).execution_passes == 1
        for result in (GateResult.FAIL, GateResult.TIMEOUT):
            assert must_accept(state, GatesRun(run=1, result=result)).execution_passes == 1

    def test_does_not_count_green_gates_nor_a_confirmed_suspicion(self) -> None:
        state = state_in(State.REVIEWING)
        assert must_accept(state, GatesRun(run=1, result=GateResult.PASS)).execution_passes == 0
        proposed = must_accept(
            state_in(State.EXECUTING), PlanChangeProposed(proposal=PROPOSAL, slice_=1)
        )
        assert proposed.execution_passes == 0

    def test_a_review_that_finds_nothing_is_still_a_pass(self) -> None:
        assert must_accept(state_in(State.REVIEWING), review()).execution_passes == 1

    @pytest.mark.parametrize("resetting", ["approved", "refused", "resumed"])
    def test_restarts_from_zero_at_each_act_of_the_developer(self, resetting: str) -> None:
        cases: dict[str, tuple[PlanState, Event]] = {
            "approved": (
                state_in(State.AWAITING_APPROVAL, execution_passes=3),
                PlanApproved(rev=1, overview=OV1),
            ),
            "refused": (
                state_in(State.PLAN_CHANGE_PROPOSED, execution_passes=3),
                PlanChangeRefused(proposal=PROPOSAL, why="no"),
            ),
            "resumed": (
                state_in(State.BLOCKED, execution_passes=3, before_blocked=State.FIXING),
                Resumed(),
            ),
        }
        before, event = cases[resetting]
        assert must_accept(before, event).execution_passes == 0

    def test_is_kept_across_a_block_and_a_conform_and_by_amendments_of_planning(self) -> None:
        state = state_in(State.REVIEWING, execution_passes=2)
        assert must_accept(state, Blocked(why="x")).execution_passes == 2
        assert must_accept(state, Conform(conformity="c", overview=OV1)).execution_passes == 2

    def test_the_two_phases_count_apart(self) -> None:
        state = must_accept(state_in(State.DRAFTING), check(1))
        assert (state.planning_passes, state.execution_passes) == (1, 0)


class TestCeiling:
    @pytest.mark.parametrize("ceiling", [1, 2, 3, 5])
    def test_a_pass_is_refused_once_the_counter_reached_the_ceiling(self, ceiling: int) -> None:
        for phase, passes in (("planning", check(1)), ("execution", review())):
            state = state_in(
                State.DRAFTING if phase == "planning" else State.REVIEWING,
                planning_passes=ceiling - 1,
                execution_passes=ceiling - 1,
            )
            reached = must_accept(state, passes, context(ceiling))
            refusal = must_refuse(reached, passes, context(ceiling))
            assert refusal.code is RefusalCode.CEILING

    @pytest.mark.parametrize(
        ("state", "event"),
        [
            (State.DRAFTING, check(2)),
            (State.EXECUTING, SuspicionDismissed(slice_=1, report="r")),
            (State.REVIEWING, review()),
            (State.REVIEWING, GatesRun(run=9, result=GateResult.FAIL)),
            (State.FIXING, GatesRun(run=9, result=GateResult.FAIL)),
            (State.FIXING, GatesRun(run=9, result=GateResult.TIMEOUT)),
        ],
    )
    def test_every_kind_of_pass_is_refused_at_the_ceiling(self, state: State, event: Event) -> None:
        prev = state_in(state, planning_passes=3, execution_passes=3)
        assert must_refuse(prev, event, context(3)).code is RefusalCode.CEILING

    @pytest.mark.parametrize(
        ("state", "event"),
        [
            (State.DRAFTING, check(0)),
            (State.REVIEWING, GatesRun(run=9, result=GateResult.PASS)),
            (State.FIXING, GatesRun(run=9, result=GateResult.PASS)),
            (State.EXECUTING, PlanChangeProposed(proposal=PROPOSAL, slice_=1)),
            (State.REVIEWING, Conform(conformity="c", overview=OV1)),
            (State.REVIEWING, Blocked(why="ceiling")),
            (State.FIXING, Blocked(why="ceiling")),
        ],
    )
    def test_what_is_not_a_pass_goes_through_at_the_ceiling(
        self, state: State, event: Event
    ) -> None:
        prev = state_in(state, planning_passes=3, execution_passes=3)
        assert must_accept(prev, event, context(3))

    def test_a_review_that_reached_the_ceiling_with_a_break_leaves_the_hand_to_the_developer(
        self,
    ) -> None:
        prev = state_in(State.REVIEWING, execution_passes=2)
        broken = ReviewDone(
            pass_=3, report="r", defects=0, deviations=0, breaks=1, proposal=PROPOSAL
        )
        assert must_accept(prev, broken, context(3)).state is State.PLAN_CHANGE_PROPOSED

    def test_a_relaunch_starts_a_new_count(self) -> None:
        """At the ceiling the loop stops, `resumed` brings the counter to zero."""
        state = replay(GATED)
        for _ in range(3):
            state = must_accept(state, review(defects=1), context(3))
            state = must_accept(state, GatesRun(run=2, result=GateResult.PASS), context(3))
            state = must_accept(state, _fix_done(), context(3))
            state = must_accept(state, GatesRun(run=3, result=GateResult.PASS), context(3))
        assert state.execution_passes == 3
        assert must_refuse(state, review(), context(3)).code is RefusalCode.CEILING
        blocked = must_accept(state, Blocked(why="ceiling reached"), context(3))
        resumed = must_accept(blocked, Resumed(), context(3))
        assert resumed.execution_passes == 0
        assert must_accept(resumed, review(), context(3)).execution_passes == 1

    def test_the_developer_can_amend_from_the_blocked_state(self) -> None:
        blocked = state_in(State.BLOCKED, execution_passes=3, before_blocked=State.EXECUTING)
        drafting = must_accept(blocked, AmendmentReceived(), context(3))
        assert drafting.state is State.DRAFTING
        assert drafting.planning_passes == 0


def _fix_done() -> Event:
    from surface_status.events import FixDone  # noqa: PLC0415

    return FixDone(pass_=1)


def test_the_fixture_journals_used_here_are_consistent() -> None:
    assert replay(CHECKED).state is State.DRAFTING
    assert replay(EXECUTING).state is State.EXECUTING
    assert replay(FIXING).state is State.FIXING
    assert replay(REVIEWING).state is State.REVIEWING
