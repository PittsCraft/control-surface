"""The derived numbers of `record` agree with the journals the machine replays (ADR 0012)."""

from pathlib import Path

import pytest

from surface_status.build import current_revision, next_review_pass
from surface_status.events import CheckDone, Event, PlanApproved, PlanDrafted, ReviewDone
from surface_status.journal import read_events

JOURNALS = sorted((Path(__file__).resolve().parents[1] / "fixtures" / "journals").glob("*.jsonl"))


def test_there_are_journals_to_replay() -> None:
    assert len(JOURNALS) >= 20


@pytest.mark.parametrize("path", JOURNALS, ids=lambda path: path.stem)
def test_the_revision_derived_before_each_event_is_the_one_recorded(path: Path) -> None:
    events = read_events(path)
    for index, event in enumerate(events):
        if isinstance(event, CheckDone | PlanDrafted | PlanApproved):
            assert current_revision(events[:index]) == event.rev, (index, event)


@pytest.mark.parametrize("path", JOURNALS, ids=lambda path: path.stem)
def test_the_review_pass_derived_before_each_review_is_the_one_recorded(path: Path) -> None:
    events: list[Event] = read_events(path)
    for index, event in enumerate(events):
        if isinstance(event, ReviewDone):
            assert next_review_pass(events[:index]) == event.pass_, (index, event)
