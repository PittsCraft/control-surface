"""The measures of a run, computed from its folder (evals/surface_evals/measure.py)."""

import json
from pathlib import Path

import pytest
from support import BLUEPRINT, case, kept_run, stream

from surface_evals.corpus import Diagram
from surface_evals.measure import EXECUTION, ZONES, cost_of, measure
from surface_evals.runner import STOPPED, stops_at_hand_over
from surface_evals.sessions import read_log

JOURNAL: list[dict[str, object]] = [
    {"event": "plan-opened"},
    {"event": "interview-closed"},
    {"event": "check-done", "omissions": 2},
    {"event": "check-done", "omissions": 0},
    {"event": "plan-drafted"},
    {"event": "plan-approved"},
    {"event": "slice-done"},
    {"event": "gates-run", "result": "fail"},
    {"event": "gates-run", "result": "pass"},
    {"event": "review-done", "defects": 1, "deviations": 0, "breaks": 0},
    {"event": "fix-done"},
    {"event": "review-done", "defects": 0, "deviations": 0, "breaks": 0},
    {"event": "conformant"},
]


def _stop(number: int, kind: str, said: str, state: str, final: str) -> dict[str, object]:
    """Make a stop as a run records it, with the stream of its session."""
    log = f"logs/{number:02d}-{kind}.jsonl"
    return {"kind": kind, "said": said, "log": log, "state": state, "final": final, "ended": True}


STOPS: list[dict[str, object]] = [
    _stop(1, "need", "/surface-plan x", "interview", "Q?"),
    _stop(2, "answer", "A.", "awaiting-approval", "Read."),
    _stop(3, "agreement", "Go.", "awaiting-approval", "No."),
    _stop(4, "approval", "/surface-execute", "conformant", "Done."),
]
# What a run that stops at the hand over leaves: the journal up to the revision handed over,
# and the stops of planning.
DRAFTED: list[dict[str, object]] = JOURNAL[:5]
PLANNED: list[dict[str, object]] = STOPS[:3]
CONFORMITY = "# Conformity\n\n```critical-files\nlending/fines.py\n```\n"
ZONED = BLUEPRINT.replace(
    "Critical zones touched, among those the repository's agent instructions declare: none.",
    "Critical zone touched: the fine computation (`lending/fines.py`).",
)


def test_a_conformant_run_is_measured_from_its_journal_its_documents_and_its_streams(
    tmp_path: Path,
) -> None:
    root = kept_run(
        tmp_path,
        journal=JOURNAL,
        stops=STOPS,
        acceptance={"ran": 8, "failed": 2, "output": ""},
        conformity="# Conformity\n",
    )
    stream(root / "logs" / "01-need.jsonl", session="plan", cost=0.2, agents=(("Plan", "opus"),))
    stream(root / "logs" / "02-answer.jsonl", session="plan", cost=1.0)
    stream(root / "logs" / "04-approval.jsonl", session="execute", cost=0.5)
    found = measure(root, case(tmp_path))
    assert found["outcome"] == "conformant"
    assert found["conformant"] is True
    assert found["handed_over"] is True
    assert found["acceptance"] == pytest.approx(0.75)
    assert found["acceptance_all"] is False
    assert found["usd"] == pytest.approx(1.5)
    # Planning is the session resumed to the hand over, the launch apart.
    assert found["planning_usd"] == pytest.approx(1.0)
    # A run played whole gives every measure of the execution.
    assert [name for name in EXECUTION if found[name] is None] == []
    # The loop: one question, one rework in planning, one fix after a first review.
    assert found["questions"] == 1
    assert found["corrections"] == 0
    assert (found["checks"], found["omissions"], found["planning_passes"]) == (2, 2, 1)
    assert (found["reviews"], found["findings"], found["fixes"]) == (2, 1, 1)
    assert found["gate_runs_failed"] == 1
    assert found["approvals"] == 1
    assert found["approved_by_sentence"] is False
    assert found["hand_back"] is None
    # The plan: drafted by the built-in agent, with the markers and the gate of the host.
    assert found["plan_drafts"] == 1
    assert found["plan_models"] == ["opus"]
    assert found["plan_minimum"] is True
    # The blueprint: its frame, one section for one behavior, no diagram, as the case expects.
    assert found["frame"] is True
    assert found["numbered_headings"] == 0
    assert found["body_titles"] == ["The overdue command"]
    assert found["body_in_range"] is True
    assert found["diagram_as_expected"] is True
    assert found["closing_line"] == "the data schema, the state machines."
    assert found["cut_kept"] is None
    # The critical zones: none expected, none named, none listed.
    assert found["zones_named"] is None
    assert found["zones_none_said"] is True
    assert found["critical_files"] == []
    assert found["zones_consistent"] is True
    assert found["contaminated"] is False


def test_a_critical_zone_is_named_at_approval_and_its_files_listed_at_conformity(
    tmp_path: Path,
) -> None:
    zone = case(
        tmp_path, critical_zones=("fine computation",), critical_files=("lending/fines.py",)
    )
    named = kept_run(
        tmp_path / "named", journal=JOURNAL, blueprints=(ZONED,), conformity=CONFORMITY
    )
    found = measure(named, zone)
    assert found["zones_named"] is True
    assert found["zones_none_said"] is None
    assert found["critical_files"] == ["lending/fines.py"]
    assert found["zones_files_listed"] is True
    assert found["zones_consistent"] is True
    # The blueprint said none, and the proof of conformity lists a file of a zone all the same.
    silent = kept_run(tmp_path / "silent", journal=JOURNAL, conformity=CONFORMITY)
    found = measure(silent, zone)
    assert found["zones_named"] is False
    assert found["zones_files_listed"] is True
    assert found["zones_consistent"] is False


def test_the_host_declares_the_zones_the_measures_look_for() -> None:
    declared = (Path(__file__).resolve().parents[2] / "evals/host/AGENTS.md").read_text("utf-8")
    zones = declared.split("## Critical zones", 1)[1]
    for phrase in ZONES:
        assert phrase in zones, phrase


def test_a_run_that_never_handed_over_has_no_form_to_measure(tmp_path: Path) -> None:
    root = kept_run(
        tmp_path, journal=JOURNAL[:1], outcome="planning-stuck", blueprints=(BLUEPRINT,)
    )
    (root / "blueprint-rev-01.md").unlink()
    record = (root / "run.json").read_text(encoding="utf-8")
    (root / "run.json").write_text(
        record.replace('["blueprint-rev-01.md"]', "[]"), encoding="utf-8"
    )
    found = measure(root, case(tmp_path))
    assert found["handed_over"] is False
    assert found["conformant"] is False
    assert found["acceptance"] is None
    assert "frame" not in found
    assert found["zones_named"] is None
    assert found["critical_files"] is None


@pytest.mark.parametrize("outcome", [STOPPED, "planning-stuck"])
def test_a_run_that_stops_at_the_hand_over_holds_no_measure_of_the_execution(
    tmp_path: Path, outcome: str
) -> None:
    root = kept_run(
        tmp_path, journal=DRAFTED, outcome=outcome, stops=PLANNED, stop_at_hand_over=True
    )
    stream(root / "logs" / "01-need.jsonl", session="plan", cost=0.2, agents=(("Plan", "opus"),))
    stream(root / "logs" / "01-developer.jsonl", session="developer", cost=0.01)
    stream(root / "logs" / "03-agreement.jsonl", session="plan", cost=1.0)
    found = measure(root, case(tmp_path))
    assert found["outcome"] == outcome
    # Planning is measured as in a run played whole: the interview, the cross-check, the page.
    assert found["handed_over"] is True
    assert (found["questions"], found["corrections"]) == (1, 0)
    assert (found["checks"], found["omissions"], found["planning_passes"]) == (2, 2, 1)
    assert found["approved_by_sentence"] is False
    assert found["plan_minimum"] is True
    assert found["frame"] is True
    assert found["zones_none_said"] is True
    assert found["contaminated"] is False
    assert found["planning_usd"] == pytest.approx(1.01)
    # Nothing of the execution is a 0 or a False, which would read as a run that did not conform.
    assert {name: found[name] for name in EXECUTION} == dict.fromkeys(EXECUTION)


def test_a_record_older_than_the_option_is_a_run_played_whole(tmp_path: Path) -> None:
    root = kept_run(tmp_path, journal=JOURNAL, stops=STOPS)
    record = json.loads((root / "run.json").read_text(encoding="utf-8"))
    del record["stop_at_hand_over"]
    (root / "run.json").write_text(json.dumps(record), encoding="utf-8")
    assert stops_at_hand_over(root) is False
    found = measure(root, case(tmp_path))
    assert found["conformant"] is True
    assert found["approvals"] == 1


def test_the_cut_of_a_revision_is_compared_with_the_one_before(tmp_path: Path) -> None:
    amended = BLUEPRINT.replace("one line per late loan", "one line per late loan, with its fine")
    kept = kept_run(tmp_path / "kept", journal=JOURNAL, blueprints=(BLUEPRINT, amended))
    assert measure(kept, case(tmp_path))["cut_kept"] is True
    recut = BLUEPRINT.replace("## The overdue command", "## The loans\n\nRead.\n\n## The order")
    moved = kept_run(tmp_path / "moved", journal=JOURNAL, blueprints=(BLUEPRINT, recut))
    found = measure(moved, case(tmp_path))
    assert found["cut_kept"] is False
    assert found["body_sections"] == 2
    assert found["body_in_range"] is False


def test_a_diagram_is_expected_where_the_case_says_the_feature_has_a_shape(tmp_path: Path) -> None:
    root = kept_run(tmp_path, journal=JOURNAL)
    assert measure(root, case(tmp_path, diagram=Diagram.SOME))["diagram_as_expected"] is False
    assert measure(root, case(tmp_path, diagram=Diagram.EITHER))["diagram_as_expected"] is None


def test_a_session_that_reads_the_clone_marks_the_run(tmp_path: Path) -> None:
    root = kept_run(tmp_path, journal=JOURNAL)
    stream(root / "logs" / "01-need.jsonl", reads=("/clone/evals/cases/01-overdue-list/brief.md",))
    assert measure(root, case(tmp_path))["contaminated"] is True


def test_the_cost_of_a_resumed_session_is_counted_once(tmp_path: Path) -> None:
    logs = [
        read_log(stream(tmp_path / "a.jsonl", session="plan", cost=0.2)),
        read_log(stream(tmp_path / "b.jsonl", session="plan", cost=0.9)),
        read_log(stream(tmp_path / "c.jsonl", session="execute", cost=0.4)),
    ]
    assert cost_of(logs) == pytest.approx(1.3)
