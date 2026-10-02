"""The event list is closed, complete and immutable."""

import dataclasses
from typing import get_args

import pytest
from state_support import valid_event

from surface_status.events import EVENT_NAMES, EVENT_TYPES, Event, InterviewClosed

SPECS_EVENTS = (
    "plan-opened",
    "interview-closed",
    "check-done",
    "plan-drafted",
    "amendment-received",
    "plan-approved",
    "slice-done",
    "plan-amended",
    "break-suspected",
    "suspicion-dismissed",
    "plan-change-proposed",
    "gates-run",
    "review-done",
    "fix-done",
    "plan-change-accepted",
    "plan-change-refused",
    "blocked",
    "resumed",
    "conform",
    "abandoned",
)


def test_the_list_is_the_nineteen_events_of_the_specs_and_the_suspected_break() -> None:
    assert EVENT_NAMES == SPECS_EVENTS
    assert len(set(EVENT_NAMES)) == 20


def test_the_union_and_the_list_hold_the_same_types() -> None:
    assert set(get_args(Event)) == set(EVENT_TYPES)


@pytest.mark.parametrize("name", SPECS_EVENTS)
def test_every_event_is_a_frozen_dataclass(name: str) -> None:
    event = valid_event(name)
    assert event.name == name
    assert hash(event) == hash(event)  # frozen, so hashable
    with pytest.raises((AttributeError, TypeError)):  # a frozen slots class raises either
        event.name = "other"  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


def test_the_own_fields_follow_the_specs() -> None:
    own = {kind.name: [f.name for f in dataclasses.fields(kind)] for kind in EVENT_TYPES}
    assert own["check-done"] == ["rev", "report", "omissions", "blueprint", "plan"]
    assert own["plan-drafted"] == ["rev", "blueprint", "plan", "slices", "gates"]
    assert own["plan-amended"] == ["slice_", "why", "plan", "slices"]
    assert own["break-suspected"] == ["slice_", "why"]
    assert own["review-done"] == [
        "pass_",
        "report",
        "defects",
        "deviations",
        "breaks",
        "proposal",
    ]
    assert own["interview-closed"] == []
    assert InterviewClosed() == InterviewClosed()
