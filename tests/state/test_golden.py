"""The golden journals: tricky paths through the machine, each expected to end where it says."""

import json
from pathlib import Path
from typing import Any

import pytest
from state_support import FIXTURES, load_journal

from surface_status.guards import InvalidJournalError, RefusalCode, fold
from surface_status.machine import State

JOURNALS = sorted(FIXTURES.glob("*.jsonl"))

REQUIRED = {
    # Breaks, suspicions and blocks, then an abandonment from every state in progress.
    "break-accepted-then-resumed",
    "suspicion-dismissed-then-confirmed",
    # a suspected break, kept in the journal until a reviewer judges it
    "suspected-break-awaiting-judgment",
    "suspected-break-dismissed-then-finished",
    "suspected-break-confirmed",
    "suspected-break-kept-across-a-block",
    "blocks-and-resumes",
    "block-in-execution-then-amendment-and-approval",
    *{
        f"abandon-from-{name}"
        for name in (
            "interview",
            "drafting",
            "awaiting-approval",
            "executing",
            "reviewing",
            "fixing",
            "plan-change-proposed",
            "blocked",
        )
    },
    # refusals, and the ceiling reached by a fix
    "refusal-from-slice",
    "refusal-from-review",
    "fix-done-at-ceiling-then-blocked",
    "fix-without-review-then-conform",
}


def test_the_fixtures_hold_every_path_the_plan_names() -> None:
    assert {path.stem for path in JOURNALS} >= REQUIRED


@pytest.mark.parametrize("path", JOURNALS, ids=lambda path: path.stem)
def test_a_golden_journal_replays_to_its_expected_state(path: Path) -> None:
    expected: dict[str, Any] = json.loads(path.with_suffix(".expected.json").read_text())
    journal = load_journal(path)
    state = fold(journal)
    assert state is not None
    assert state.state == State(expected["state"])
    assert list(state.remaining) == expected["remaining"]
    assert sorted(state.done) == expected["done"]
    assert state.planning_passes == expected["planning_passes"]
    assert state.execution_passes == expected["execution_passes"]
    before_blocked = None if state.before_blocked is None else state.before_blocked.value
    assert before_blocked == expected["before_blocked"]
    origin = None if state.proposal_origin is None else state.proposal_origin.value
    assert origin == expected["proposal_origin"]
    suspicion = state.suspicion
    shown = None if suspicion is None else {"slice": suspicion.slice_, "why": suspicion.why}
    assert shown == expected.get("suspicion")
    if "before_last" in expected:
        before = fold(journal[:-1])
        assert before is not None
        assert before.state.value == expected["before_last"]


def test_every_journal_has_its_expected_file_and_the_reverse() -> None:
    expected = {
        path.name.removesuffix(".expected.json") for path in FIXTURES.glob("*.expected.json")
    }
    assert expected == {path.stem for path in JOURNALS}


def test_a_hand_edited_journal_does_not_replay() -> None:
    journal = load_journal(FIXTURES / "refusal-from-slice.jsonl")
    edited = [*journal[:6], journal[5], *journal[6:]]  # the same slice recorded twice
    with pytest.raises(InvalidJournalError) as error:
        fold(edited)
    assert error.value.index == 6
    assert error.value.refusal.code is RefusalCode.SLICE
    assert "line 7" in str(error.value)


def test_a_journal_must_start_with_plan_opened() -> None:
    journal = load_journal(FIXTURES / "abandon-from-drafting.jsonl")
    with pytest.raises(InvalidJournalError) as error:
        fold(journal[1:])
    assert error.value.refusal.code is RefusalCode.TRANSITION


def test_an_empty_journal_has_no_state() -> None:
    assert fold([]) is None
