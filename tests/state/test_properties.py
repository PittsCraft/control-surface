"""Replay as properties: any accepted sequence ends in a listed state, and it is deterministic."""

from unittest import TestCase

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    rule,
)
from state_strategies import Run, contexts, events, runs
from state_support import EXPECTED

from surface_status.events import (
    CheckDone,
    Conform,
    Event,
    FixDone,
    GateResult,
    GatesRun,
    PlanAmended,
    ReviewDone,
    SliceDone,
    SuspicionDismissed,
)
from surface_status.guards import Accepted, RecordContext, Refusal, RefusalCode, admit, fold
from surface_status.machine import PlanState, State


def raises_a_counter(prev: PlanState, event: Event) -> int | None:
    """Independent statement of the ceiling rules: the counter an event raises, if it is a pass."""
    if isinstance(event, CheckDone) and event.omissions > 0:
        return prev.planning_passes
    if isinstance(event, ReviewDone | SuspicionDismissed):
        return prev.execution_passes
    if isinstance(event, GatesRun) and event.result is not GateResult.PASS:
        return prev.execution_passes
    return None


def check_attempt(
    prev: PlanState | None, event: Event, context: RecordContext, result: Accepted | Refusal
) -> None:
    departure = None if prev is None else prev.state
    allowed = EXPECTED[event.name].get(departure)
    if allowed is None:
        assert isinstance(result, Refusal)
        assert result.code is RefusalCode.TRANSITION
        return
    if prev is not None:
        passes = raises_a_counter(prev, event)
        if passes is not None and passes >= context.ceiling:
            assert isinstance(result, Refusal), "a pass was accepted beyond the ceiling"
        if isinstance(event, SliceDone | PlanAmended | FixDone | Conform) and (
            context.overview_hash != prev.approved_overview
        ):
            assert isinstance(result, Refusal), "the overview changed after approval"
    if isinstance(result, Accepted):
        assert result.state.state in allowed
        assert result.state.planning_passes <= context.ceiling
        assert result.state.execution_passes <= context.ceiling


@given(runs())
def test_every_attempt_obeys_the_table_and_the_guards(run: Run) -> None:
    for attempt in run.attempts:
        result = admit(attempt.prev, attempt.event, attempt.context)
        check_attempt(attempt.prev, attempt.event, attempt.context, result)


@given(runs())
def test_an_accepted_sequence_ends_in_a_listed_state_and_replays_the_same(run: Run) -> None:
    state: PlanState | None = None
    accepted: list[Event] = []
    for attempt in run.attempts:
        result = admit(state, attempt.event, attempt.context)
        if isinstance(result, Accepted):
            accepted.append(attempt.event)
            state = result.state
    if state is None:
        assert accepted == []
        return
    assert state.state in set(State)
    assert fold(accepted) == state
    assert fold(list(accepted)) == fold(iter(accepted))


@given(runs())
def test_a_refusal_changes_nothing_and_a_terminal_state_stays(run: Run) -> None:
    state: PlanState | None = None
    for attempt in run.attempts:
        before = state
        result = admit(state, attempt.event, attempt.context)
        if isinstance(result, Accepted):
            assert before is None or not before.terminal
            state = result.state
        else:
            assert state == before


def test_the_generator_walks_through_all_ten_states() -> None:
    seen: set[State] = set()

    @settings(derandomize=True, max_examples=300, database=None)
    @given(runs())
    def walk(run: Run) -> None:
        state: PlanState | None = None
        for attempt in run.attempts:
            result = admit(state, attempt.event, attempt.context)
            if isinstance(result, Accepted):
                state = result.state
                seen.add(state.state)

    walk()
    assert seen == set(State)


class PlanMachine(RuleBasedStateMachine):
    """A plan driven event by event, checking the invariants after each step."""

    def __init__(self) -> None:
        super().__init__()
        self.ceiling = 3
        self.state: PlanState | None = None
        self.journal: list[Event] = []

    @initialize(ceiling=st.integers(1, 4))
    def choose_ceiling(self, ceiling: int) -> None:
        self.ceiling = ceiling

    @rule(data=st.data())
    def attempt(self, data: st.DataObject) -> None:
        context = data.draw(contexts(self.state, self.ceiling))
        event = data.draw(events(self.state))
        result = admit(self.state, event, context)
        check_attempt(self.state, event, context, result)
        if isinstance(result, Accepted):
            self.journal.append(event)
            self.state = result.state

    @invariant()
    def the_state_is_the_replay_of_the_journal(self) -> None:
        assert fold(self.journal) == self.state

    @invariant()
    def the_counters_stay_within_the_ceiling(self) -> None:
        if self.state is not None:
            assert 0 <= self.state.planning_passes <= self.ceiling
            assert 0 <= self.state.execution_passes <= self.ceiling

    @invariant()
    def the_slices_done_and_the_state_are_coherent(self) -> None:
        if self.state is not None and self.state.state is State.EXECUTING:
            assert self.state.remaining


TestPlanMachine: type[TestCase] = PlanMachine.TestCase  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
