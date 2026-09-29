"""Every pair (event, state) the table does not hold is refused, over all 19 x 10 pairs."""

import pytest
from state_support import CONTEXT, EXPECTED, state_in, valid_event

from surface_status.events import EVENT_NAMES
from surface_status.guards import Accepted, RecordContext, Refusal, RefusalCode, admit
from surface_status.machine import TRANSITIONS, State

STATES = list(State)
PAIRS = [(name, state) for name in EVENT_NAMES for state in STATES]


def test_there_are_ten_states_and_200_pairs() -> None:
    assert len(STATES) == 10
    assert len(PAIRS) == 200


def test_the_table_is_the_expected_one() -> None:
    assert set(TRANSITIONS) == set(EXPECTED)
    for name, departures in EXPECTED.items():
        assert set(TRANSITIONS[name]) == set(departures), name


@pytest.mark.parametrize(("name", "state"), PAIRS)
@pytest.mark.parametrize("context", [None, CONTEXT], ids=["replay", "record"])
def test_a_pair_is_accepted_exactly_when_the_table_says_so(
    name: str, state: State, context: RecordContext | None
) -> None:
    result = admit(state_in(state), valid_event(name), context)
    allowed = EXPECTED[name].get(state)
    if allowed is None:
        assert isinstance(result, Refusal)
        assert result.code is RefusalCode.TRANSITION
    else:
        assert isinstance(result, Accepted), result
        assert result.state.state in allowed


@pytest.mark.parametrize("name", EVENT_NAMES)
def test_only_plan_opened_starts_a_journal(name: str) -> None:
    result = admit(None, valid_event(name), CONTEXT)
    if name == "plan-opened":
        assert isinstance(result, Accepted)
        assert result.state.state is State.INTERVIEW
    else:
        assert isinstance(result, Refusal)
        assert result.code is RefusalCode.TRANSITION


@pytest.mark.parametrize("state", [State.CONFORM, State.ABANDONED])
@pytest.mark.parametrize("name", EVENT_NAMES)
def test_terminal_states_accept_nothing(name: str, state: State) -> None:
    assert not isinstance(admit(state_in(state), valid_event(name), CONTEXT), Accepted)


def test_the_accepted_pairs_number_32() -> None:
    accepted = [
        (name, state)
        for name, state in PAIRS
        if isinstance(admit(state_in(state), valid_event(name)), Accepted)
    ]
    assert len(accepted) == 32
