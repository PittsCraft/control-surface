"""The guards of the state machine, one behavior per test (ADR 0011)."""

import pytest
from state_support import (
    AWAITING,
    CHECKED,
    CONTEXT,
    DRAFTING,
    EXECUTING,
    FIXING,
    GATED,
    OV1,
    OV2,
    PL1,
    PL2,
    PROPOSAL,
    REVIEWING,
    must_accept,
    must_refuse,
    replay,
    state_in,
)

from surface_status.events import (
    CheckDone,
    Conform,
    Event,
    FixDone,
    GateResult,
    GatesRun,
    PlanAmended,
    PlanApproved,
    PlanDrafted,
    ReviewDone,
    SliceDone,
)
from surface_status.guards import RecordContext, RefusalCode
from surface_status.machine import State

CHANGED = RecordContext(ceiling=3, gates_declared=True, overview_hash=OV2)
UNREAD = RecordContext(ceiling=3, gates_declared=True, overview_hash=None)
NO_GATES = RecordContext(ceiling=3, gates_declared=False, overview_hash=OV1)


def test_a_slice_a_fix_an_amendment_and_conformity_are_refused_once_the_overview_changed() -> None:
    """The frozen overview: `overview.md` differs from the last `plan-approved`."""
    cases: list[tuple[State, Event]] = [
        (State.EXECUTING, SliceDone(slice_=1, gates="lint")),
        (State.EXECUTING, PlanAmended(slice_=1, why="x", plan=PL2, slices=(1, 2))),
        (State.FIXING, PlanAmended(slice_=1, why="x", plan=PL2, slices=(1, 2))),
        (State.FIXING, FixDone(pass_=1)),
        (State.REVIEWING, Conform(conformity="conformity.md", overview=OV1)),
    ]
    for state, event in cases:
        prev = state_in(state)
        assert must_accept(prev, event, CONTEXT)
        for context in (CHANGED, UNREAD):
            refusal = must_refuse(prev, event, context)
            assert refusal.code is RefusalCode.OVERVIEW_CHANGED, (state, event)


def test_conformity_carries_the_hash_it_was_computed_from_and_replay_checks_it() -> None:
    prev = state_in(State.REVIEWING)
    refusal = must_refuse(prev, Conform(conformity="conformity.md", overview=OV2), None)
    assert refusal.code is RefusalCode.OVERVIEW_CHANGED


def test_the_events_that_are_not_guarded_ignore_the_overview_hash() -> None:
    prev = state_in(State.REVIEWING)
    review = ReviewDone(pass_=1, report="r", defects=0, deviations=0, breaks=0)
    assert must_accept(prev, review, CHANGED)
    assert must_accept(prev, GatesRun(run=2, result=GateResult.PASS), CHANGED)


class TestPlanDrafted:
    def drafted(self, **changes: object) -> PlanDrafted:
        fields: dict[str, object] = {"rev": 1, "overview": OV1, "plan": PL1, "slices": (1, 2)}
        return PlanDrafted(**{**fields, **changes})  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    def test_needs_a_cross_check_of_the_revision(self) -> None:
        prev = replay(DRAFTING)
        assert must_refuse(prev, self.drafted()).code is RefusalCode.CROSS_CHECK

    def test_is_refused_when_the_last_check_counts_omissions(self) -> None:
        prev = replay(
            [*DRAFTING, CheckDone(rev=1, report="r", omissions=2, overview=OV1, plan=PL1)]
        )
        assert must_refuse(prev, self.drafted()).code is RefusalCode.CROSS_CHECK

    def test_is_refused_when_the_check_covered_other_hashes(self) -> None:
        prev = replay(CHECKED)
        assert must_refuse(prev, self.drafted(overview=OV2)).code is RefusalCode.CROSS_CHECK
        assert must_refuse(prev, self.drafted(plan=PL2)).code is RefusalCode.CROSS_CHECK

    def test_is_refused_when_the_check_is_of_another_revision(self) -> None:
        assert must_refuse(replay(CHECKED), self.drafted(rev=2)).code is RefusalCode.CROSS_CHECK

    def test_uses_the_last_check_only(self) -> None:
        events = [
            *CHECKED,
            CheckDone(rev=1, report="r2", omissions=1, overview=OV1, plan=PL1),
        ]
        assert must_refuse(replay(events), self.drafted()).code is RefusalCode.CROSS_CHECK
        events.append(CheckDone(rev=1, report="r3", omissions=0, overview=OV1, plan=PL1))
        assert must_accept(replay(events), self.drafted()).declared == {1, 2}


def test_approval_needs_the_overview_of_the_last_draft() -> None:
    prev = replay(AWAITING)
    assert must_refuse(prev, PlanApproved(rev=1, overview=OV2)).code is RefusalCode.DRAFT_HASH
    assert must_accept(prev, PlanApproved(rev=1, overview=OV1)).approved_overview == OV1


def test_a_slice_must_be_declared_and_not_done() -> None:
    prev = replay(EXECUTING)
    assert must_refuse(prev, SliceDone(slice_=9, gates="g")).code is RefusalCode.SLICE
    once = must_accept(prev, SliceDone(slice_=1, gates="g"))
    assert must_refuse(once, SliceDone(slice_=1, gates="g")).code is RefusalCode.SLICE


def test_a_fix_cannot_change_the_list_of_slices() -> None:
    prev = replay(FIXING)
    for slices in ((1,), (1, 2, 3)):
        event = PlanAmended(slice_=1, why="x", plan=PL2, slices=slices)
        assert must_refuse(prev, event).code is RefusalCode.SLICE_LIST
    same = PlanAmended(slice_=1, why="x", plan=PL2, slices=(2, 1))
    assert must_accept(prev, same).declared == {1, 2}


def test_an_amendment_in_a_slice_may_change_the_list() -> None:
    event = PlanAmended(slice_=1, why="split", plan=PL2, slices=(1, 2, 3))
    assert must_accept(replay(EXECUTING), event).declared == {1, 2, 3}


class TestReview:
    def review(self, **changes: object) -> ReviewDone:
        fields: dict[str, object] = {
            "pass_": 1,
            "report": "reviews/pass-01.md",
            "defects": 0,
            "deviations": 0,
            "breaks": 0,
        }
        return ReviewDone(**{**fields, **changes})  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    def test_a_break_needs_a_proposal(self) -> None:
        prev = replay(GATED)
        assert must_refuse(prev, self.review(breaks=1)).code is RefusalCode.PROPOSAL
        assert must_accept(prev, self.review(breaks=1, proposal=PROPOSAL))

    def test_needs_green_gates_since_the_last_slice(self) -> None:
        prev = replay(REVIEWING)
        assert must_refuse(prev, self.review()).code is RefusalCode.GATES
        failed = must_accept(prev, GatesRun(run=1, result=GateResult.FAIL))
        assert failed.state is State.FIXING
        assert must_refuse(
            state_in(State.REVIEWING, gates=GateResult.FAIL), self.review()
        ).code is (RefusalCode.GATES)
        assert must_refuse(state_in(State.REVIEWING, gates=None), self.review()).code is (
            RefusalCode.GATES
        )

    def test_needs_new_gates_after_each_review(self) -> None:
        reviewed = must_accept(replay(GATED), self.review())
        assert must_refuse(reviewed, self.review(pass_=2)).code is RefusalCode.GATES

    def test_is_free_of_gates_when_the_project_declares_none(self) -> None:
        assert must_accept(replay(REVIEWING), self.review(), NO_GATES)


class TestFixDone:
    def test_needs_a_green_gate_run_right_before(self) -> None:
        prev = replay(FIXING)
        assert must_refuse(prev, FixDone(pass_=1)).code is RefusalCode.GATES
        green = must_accept(prev, GatesRun(run=2, result=GateResult.PASS))
        assert must_accept(green, FixDone(pass_=1)).state is State.REVIEWING

    def test_is_refused_when_an_amendment_came_after_the_gate_run(self) -> None:
        green = must_accept(replay(FIXING), GatesRun(run=2, result=GateResult.PASS))
        amended = must_accept(green, PlanAmended(slice_=1, why="x", plan=PL2, slices=(1, 2)))
        assert must_refuse(amended, FixDone(pass_=1)).code is RefusalCode.GATES

    def test_is_refused_after_a_failed_run(self) -> None:
        failed = must_accept(replay(FIXING), GatesRun(run=2, result=GateResult.TIMEOUT))
        assert must_refuse(failed, FixDone(pass_=1)).code is RefusalCode.GATES

    def test_is_free_of_gates_when_the_project_declares_none(self) -> None:
        assert must_accept(replay(FIXING), FixDone(pass_=1), NO_GATES).state is State.REVIEWING


class TestConform:
    conform = Conform(conformity="conformity.md", overview=OV1)

    def clean(self) -> ReviewDone:
        return ReviewDone(pass_=1, report="r", defects=0, deviations=0, breaks=0)

    @pytest.mark.parametrize(("defects", "deviations"), [(1, 0), (0, 1), (3, 2)])
    def test_is_refused_when_the_last_review_found_something(
        self, defects: int, deviations: int
    ) -> None:
        prev = state_in(State.REVIEWING, last_review=None)
        review = ReviewDone(pass_=1, report="r", defects=defects, deviations=deviations, breaks=0)
        found = must_accept(state_in(State.REVIEWING), review)
        assert found.state is State.FIXING
        seen = state_in(State.REVIEWING, last_review=found.last_review)
        assert must_refuse(seen, self.conform).code is RefusalCode.CONFORMITY
        assert must_refuse(prev, self.conform).code is RefusalCode.CONFORMITY

    def test_is_accepted_after_a_clean_review(self) -> None:
        reviewed = must_accept(replay(GATED), self.clean())
        assert must_accept(reviewed, self.conform).state is State.CONFORM

    def test_needs_a_review_since_the_last_change_of_the_work(self) -> None:
        """A clean review, then a failed gate run and a fix, leaves no review standing."""
        reviewed = must_accept(replay(GATED), self.clean())
        failed = must_accept(reviewed, GatesRun(run=2, result=GateResult.FAIL))
        green = must_accept(failed, GatesRun(run=3, result=GateResult.PASS))
        fixed = must_accept(green, FixDone(pass_=1))
        assert fixed.state is State.REVIEWING
        assert must_refuse(fixed, self.conform).code is RefusalCode.CONFORMITY
