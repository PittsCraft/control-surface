"""The pass counters, reset by each act of the developer, and the loop they bound."""

from collections.abc import Callable
from dataclasses import dataclass, replace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from state_support import (
    BP1,
    CHECKED,
    DRAFTING,
    EXECUTING,
    FIXING,
    GATED,
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
    BreakSuspected,
    CheckDone,
    Conform,
    Event,
    FixDone,
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
    SliceDone,
    SuspicionDismissed,
)
from surface_status.guards import RecordContext, RefusalCode
from surface_status.machine import PlanState, State, sends_work_back


def context(ceiling: int) -> RecordContext:
    return RecordContext(ceiling=ceiling, gates_declared=True, blueprint_hash=BP1)


def check(omissions: int) -> CheckDone:
    return CheckDone(rev=1, report="r", omissions=omissions, blueprint=BP1, plan=PL1)


def review(*, defects: int = 0, deviations: int = 0) -> ReviewDone:
    return ReviewDone(pass_=1, report="r", defects=defects, deviations=deviations, breaks=0)


BROKEN = ReviewDone(pass_=1, report="r", defects=0, deviations=0, breaks=1, proposal=PROPOSAL)
FAILED = GatesRun(run=9, result=GateResult.FAIL)


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
        drafted = must_accept(state, PlanDrafted(rev=1, blueprint=BP1, plan=PL1, slices=(1, 2)))
        assert drafted.planning_passes == 1

    def test_the_execution_events_leave_it_alone(self) -> None:
        state = state_in(State.REVIEWING, planning_passes=2)
        assert must_accept(state, review(defects=1)).planning_passes == 2


class TestExecution:
    @pytest.mark.parametrize(
        ("state", "event"),
        [
            (State.EXECUTING, SuspicionDismissed(slice_=1, report="r")),
            (State.REVIEWING, review(defects=1)),
            (State.REVIEWING, review(deviations=2)),
            (State.REVIEWING, GatesRun(run=1, result=GateResult.FAIL)),
            (State.REVIEWING, GatesRun(run=1, result=GateResult.TIMEOUT)),
            (State.FIXING, GatesRun(run=1, result=GateResult.FAIL)),
            (State.FIXING, GatesRun(run=1, result=GateResult.TIMEOUT)),
        ],
    )
    def test_counts_what_sends_work_back_to_an_agent(self, state: State, event: Event) -> None:
        assert sends_work_back(event)
        assert must_accept(state_in(state), event).execution_passes == 1

    @pytest.mark.parametrize(
        ("state", "event"),
        [
            (State.REVIEWING, review()),
            (State.REVIEWING, GatesRun(run=1, result=GateResult.PASS)),
            (State.FIXING, GatesRun(run=1, result=GateResult.PASS)),
            (State.REVIEWING, BROKEN),
            (State.REVIEWING, replace(BROKEN, defects=2, deviations=1)),
            (State.EXECUTING, PlanChangeProposed(proposal=PROPOSAL, slice_=1)),
            (State.EXECUTING, BreakSuspected(slice_=1, why="x")),
            (State.EXECUTING, SliceDone(slice_=1, gates="lint")),
            (State.FIXING, FixDone(pass_=1)),
        ],
    )
    def test_counts_nothing_that_sends_no_work_back(self, state: State, event: Event) -> None:
        assert not sends_work_back(event)
        assert must_accept(state_in(state), event).execution_passes == 0

    def test_a_break_goes_to_the_developer_without_costing_a_pass(self) -> None:
        proposed = must_accept(state_in(State.REVIEWING, execution_passes=2), BROKEN)
        assert proposed.state is State.PLAN_CHANGE_PROPOSED
        assert proposed.execution_passes == 2

    def test_a_fix_whose_own_gate_run_fails_is_one_pass_and_the_next_fix_another(self) -> None:
        """One defect, a fixer whose gates fail, a second fixer, then a clean review."""
        state = must_accept(replay(GATED), review(defects=1))
        assert (state.state, state.execution_passes) == (State.FIXING, 1)
        state = must_accept(state, GatesRun(run=2, result=GateResult.FAIL))
        assert (state.state, state.execution_passes) == (State.FIXING, 2)
        state = must_accept(state, GatesRun(run=3, result=GateResult.PASS))
        state = must_accept(state, FixDone(pass_=1))
        state = must_accept(state, review())
        conform = must_accept(state, Conform(conformity="c", blueprint=BP1))
        assert (conform.state, conform.execution_passes) == (State.CONFORM, 2)

    @pytest.mark.parametrize("resetting", ["approved", "refused", "resumed"])
    def test_restarts_from_zero_at_each_act_of_the_developer(self, resetting: str) -> None:
        cases: dict[str, tuple[PlanState, Event]] = {
            "approved": (
                state_in(State.AWAITING_APPROVAL, execution_passes=3),
                PlanApproved(rev=1, blueprint=BP1),
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
        assert must_accept(state, Conform(conformity="c", blueprint=BP1)).execution_passes == 2

    def test_the_two_phases_count_apart(self) -> None:
        state = must_accept(state_in(State.DRAFTING), check(1))
        assert (state.planning_passes, state.execution_passes) == (1, 0)


class TestCeiling:
    @pytest.mark.parametrize("ceiling", [1, 2, 3, 5])
    def test_planning_records_the_pass_past_the_ceiling_and_refuses_the_next(
        self, ceiling: int
    ) -> None:
        state = state_in(State.DRAFTING, planning_passes=ceiling)
        over = must_accept(state, check(1), context(ceiling))
        assert (over.state, over.planning_passes) == (State.DRAFTING, ceiling + 1)
        assert must_refuse(over, check(1), context(ceiling)).code is RefusalCode.CEILING
        assert must_accept(over, check(0), context(ceiling)).planning_passes == ceiling + 1

    @pytest.mark.parametrize("ceiling", [1, 2, 3, 5])
    def test_execution_records_the_pass_past_the_ceiling_and_refuses_the_next(
        self, ceiling: int
    ) -> None:
        state = state_in(State.REVIEWING, execution_passes=ceiling)
        over = must_accept(state, review(defects=1), context(ceiling))
        assert (over.state, over.execution_passes) == (State.FIXING, ceiling + 1)
        assert must_refuse(over, FAILED, context(ceiling)).code is RefusalCode.CEILING

    @pytest.mark.parametrize(
        ("state", "event"),
        [
            (State.DRAFTING, check(2)),
            (State.EXECUTING, SuspicionDismissed(slice_=1, report="r")),
            (State.REVIEWING, review(defects=1)),
            (State.REVIEWING, review(deviations=1)),
            (State.REVIEWING, FAILED),
            (State.FIXING, FAILED),
            (State.FIXING, GatesRun(run=9, result=GateResult.TIMEOUT)),
        ],
    )
    def test_every_kind_of_pass_is_refused_past_the_ceiling(
        self, state: State, event: Event
    ) -> None:
        prev = state_in(state, planning_passes=4, execution_passes=4)
        assert must_refuse(prev, event, context(3)).code is RefusalCode.CEILING

    @pytest.mark.parametrize(
        ("state", "event"),
        [
            (State.DRAFTING, check(0)),
            (State.REVIEWING, review()),
            (State.REVIEWING, BROKEN),
            (State.REVIEWING, GatesRun(run=9, result=GateResult.PASS)),
            (State.FIXING, GatesRun(run=9, result=GateResult.PASS)),
            (State.EXECUTING, PlanChangeProposed(proposal=PROPOSAL, slice_=1)),
            (State.EXECUTING, BreakSuspected(slice_=1, why="x")),
            (State.REVIEWING, Conform(conformity="c", blueprint=BP1)),
            (State.REVIEWING, Blocked(why="ceiling")),
            (State.FIXING, Blocked(why="ceiling")),
        ],
    )
    def test_what_is_not_a_pass_goes_through_past_the_ceiling(
        self, state: State, event: Event
    ) -> None:
        prev = state_in(state, planning_passes=4, execution_passes=4)
        assert must_accept(prev, event, context(3))

    def test_a_relaunch_starts_a_new_count(self) -> None:
        """Past the ceiling the loop stops, `resumed` brings the counter to zero."""
        state = replay(GATED)
        for _ in range(3):
            state = must_accept(state, review(defects=1), context(3))
            state = must_accept(state, GatesRun(run=2, result=GateResult.PASS), context(3))
            state = must_accept(state, FixDone(pass_=1), context(3))
        assert state.execution_passes == 3
        state = must_accept(state, review(defects=1), context(3))
        assert state.execution_passes == 4
        assert must_refuse(state, FAILED, context(3)).code is RefusalCode.CEILING
        blocked = must_accept(state, Blocked(why="ceiling reached"), context(3))
        resumed = must_accept(blocked, Resumed(), context(3))
        assert (resumed.state, resumed.execution_passes) == (State.FIXING, 0)
        assert must_accept(resumed, FAILED, context(3)).execution_passes == 1

    def test_a_resumption_in_planning_starts_a_new_count(self) -> None:
        """Past the ceiling the loop stops, `resumed` brings the planning counter to zero."""
        state = replay(DRAFTING)
        for _ in range(4):
            state = must_accept(state, check(1), context(3))
        assert state.planning_passes == 4
        assert must_refuse(state, check(1), context(3)).code is RefusalCode.CEILING
        blocked = must_accept(state, Blocked(why="ceiling reached"), context(3))
        resumed = must_accept(blocked, Resumed(), context(3))
        assert (resumed.state, resumed.planning_passes) == (State.DRAFTING, 0)
        assert must_accept(resumed, check(1), context(3)).planning_passes == 1

    def test_the_developer_can_amend_from_the_blocked_state(self) -> None:
        blocked = state_in(State.BLOCKED, execution_passes=4, before_blocked=State.EXECUTING)
        drafting = must_accept(blocked, AmendmentReceived(), context(3))
        assert drafting.state is State.DRAFTING
        assert drafting.planning_passes == 0


# The loop of `/surface-plan`, steps 7 to 9, driven from a closed interview.


def plan_loop(ceiling: int, omissions: list[int]) -> tuple[int, PlanState]:
    """Follow steps 8 and 9 until they stop; `omissions` stands for the checker's counts.

    Return the reworks the loop sent, the extractor or the plan corrected, and where it stopped.
    """
    state = replay(DRAFTING)
    for reworks, found in enumerate(omissions):  # each turn after the first is step 7 again
        state = must_accept(state, check(found), context(ceiling))
        if found == 0:
            drafted = PlanDrafted(rev=1, blueprint=BP1, plan=PL1, slices=(1, 2))
            return reworks, must_accept(state, drafted, context(ceiling))
        if state.planning_passes > ceiling:
            return reworks, must_accept(state, Blocked(why="ceiling"), context(ceiling))
    message = "the checker ran out of answers"
    raise AssertionError(message)


class TestThePlanningLoop:
    @pytest.mark.parametrize(
        ("omissions", "reworks", "end"),
        [
            # Every check finds omissions: three reworks, and the fourth check hands back.
            ([1, 2, 1, 3], 3, State.BLOCKED),
            # The third rework converges: its clean check is recorded, then the draft.
            ([1, 2, 1, 0], 3, State.AWAITING_APPROVAL),
            # A first clean check costs nothing.
            ([0], 0, State.AWAITING_APPROVAL),
        ],
    )
    def test_a_ceiling_of_three_lets_the_blueprint_be_reworked_three_times(
        self, omissions: list[int], reworks: int, end: State
    ) -> None:
        sent, state = plan_loop(3, omissions)
        assert (sent, state.state) == (reworks, end)

    @given(st.integers(1, 4), st.lists(st.integers(0, 3), min_size=5, max_size=5))
    def test_at_most_ceiling_reworks_and_only_a_check_with_omissions_hands_back(
        self, ceiling: int, omissions: list[int]
    ) -> None:
        sent, state = plan_loop(ceiling, omissions)
        assert sent <= ceiling
        assert state.planning_passes <= ceiling + 1
        if state.state is State.BLOCKED:
            assert (sent, state.planning_passes) == (ceiling, ceiling + 1)


# The loop of `/surface-execute`, driven row by row from an approved plan of two slices.


@dataclass
class Loop:
    ceiling: int
    state: PlanState
    journal: list[Event]
    sent: int = 0  # agents sent back to work: a fixer, or an executor after a dismissal

    def record(self, event: Event) -> None:
        """Record as the loop does: the ceiling never refuses a step the loop takes."""
        self.state = must_accept(self.state, event, context(self.ceiling))
        self.journal.append(event)


FINDINGS: dict[str, ReviewDone] = {
    "clean": review(),
    "defect": review(defects=1),
    "deviation": review(deviations=1),
    "break": BROKEN,
}

Answer = Callable[[tuple[str, ...]], str]


def scripted(answers: list[str]) -> Answer:
    remaining = iter(answers)

    def answer(options: tuple[str, ...]) -> str:
        chosen = next(remaining)
        assert chosen in options
        return chosen

    return answer


def _clean_review_last(state: PlanState) -> bool:
    review = state.last_review
    return isinstance(state.last_event, ReviewDone) and review is not None and review.clean


def _step(loop: Loop, answer: Answer) -> None:  # noqa: PLR0912 (one arm per row)
    """Take the step of the first row of the loop that holds, short of the rows that stop."""
    state = loop.state
    ceiling_reached = state.execution_passes > loop.ceiling
    if ceiling_reached and not (state.state is State.REVIEWING and _clean_review_last(state)):
        loop.record(Blocked(why="ceiling"))
    elif state.state is State.EXECUTING and state.suspicion is not None:
        slice_ = state.suspicion.slice_
        if answer(("dismissed", "confirmed")) == "dismissed":
            loop.record(SuspicionDismissed(slice_=slice_, report="r"))
        else:
            loop.record(PlanChangeProposed(proposal=PROPOSAL, slice_=slice_))
    elif state.state is State.EXECUTING:
        loop.sent += isinstance(state.last_event, SuspicionDismissed)
        slice_ = state.remaining[0]
        if answer(("done", "suspected")) == "done":
            loop.record(SliceDone(slice_=slice_, gates="lint"))
        else:
            loop.record(BreakSuspected(slice_=slice_, why="x"))
    elif state.state is State.REVIEWING and _clean_review_last(state):
        loop.record(Conform(conformity="c", blueprint=BP1))
    elif state.state is State.REVIEWING and state.gates is not GateResult.PASS:
        loop.record(GatesRun(run=1, result=GateResult(answer(("pass", "fail")))))
    elif state.state is State.REVIEWING:
        loop.record(FINDINGS[answer(tuple(FINDINGS))])
    else:
        loop.sent += 1  # a fixer, whose own gate run ends its work
        if answer(("pass", "fail")) == "pass":
            loop.record(GatesRun(run=1, result=GateResult.PASS))
            loop.record(FixDone(pass_=1))
        else:
            loop.record(FAILED)


def drive(ceiling: int, answer: Answer) -> Loop:
    """Follow the loop until a row stops it; `answer` stands for the agents and the gates."""
    loop = Loop(ceiling, replay(EXECUTING), list(EXECUTING))
    while loop.state.state not in {State.CONFORM, State.PLAN_CHANGE_PROPOSED, State.BLOCKED}:
        _step(loop, answer)
    return loop


class TestTheLoop:
    @pytest.mark.parametrize(
        ("answers", "sent", "end"),
        [
            # Every review finds a defect: three fixes, and the fourth review hands back.
            (["pass", *["defect", "pass"] * 3, "defect"], 3, State.BLOCKED),
            # Every fixer's own gate run fails: three fixers, the third one's run hands back.
            (["pass", "defect", "fail", "fail", "fail"], 3, State.BLOCKED),
            # The third fix converges: its clean review is recorded, then conform.
            (["pass", *["defect", "pass"] * 3, "clean"], 3, State.CONFORM),
            # A fixer whose gates fail, a second one, then a clean review: two passes.
            (["pass", "defect", "fail", "pass", "clean"], 2, State.CONFORM),
            # A red run after the slices, then a fix that converges.
            (["fail", "pass", "clean"], 1, State.CONFORM),
        ],
    )
    def test_a_ceiling_of_three_lets_three_agents_take_the_work_back(
        self, answers: list[str], sent: int, end: State
    ) -> None:
        loop = drive(3, scripted(["done", "done", *answers]))
        assert (loop.sent, loop.state.state) == (sent, end)

    def test_a_dismissed_suspicion_sends_its_slice_back(self) -> None:
        loop = drive(1, scripted(["suspected", "dismissed", "suspected", "dismissed"]))
        assert (loop.sent, loop.state.state) == (1, State.BLOCKED)
        assert loop.state.execution_passes == 2

    @given(st.integers(1, 4), st.data())
    def test_at_most_ceiling_agents_take_the_work_back_and_only_a_pass_hands_back(
        self, ceiling: int, data: st.DataObject
    ) -> None:
        loop = drive(ceiling, lambda options: data.draw(st.sampled_from(options)))
        assert loop.sent <= ceiling
        assert loop.state.execution_passes <= ceiling + 1
        if loop.state.state is State.BLOCKED:
            assert loop.sent == ceiling
            assert sends_work_back(loop.journal[-2])


def test_the_fixture_journals_used_here_are_consistent() -> None:
    assert replay(CHECKED).state is State.DRAFTING
    assert replay(EXECUTING).state is State.EXECUTING
    assert replay(FIXING).state is State.FIXING
    assert replay(REVIEWING).state is State.REVIEWING
