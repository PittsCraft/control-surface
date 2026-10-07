"""The measures of a run, computed from its folder (evals/surface_evals/measure.py)."""

import json
from pathlib import Path

import pytest
import toy
from support import BLUEPRINT, case, gh, kept_run, stream

from surface_evals.corpus import Diagram, ExpectedCorrection
from surface_evals.measure import EXECUTION, ZONES, cost_of, measure
from surface_evals.report import DIRECTION, GOALS
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


# The pull request a stop found as the chain leaves it: a draft, with the description of then.
CURRENT = {"draft": True, "described": True}


def _stop(  # noqa: PLR0913 (what a stop records, each by its name)
    number: int,
    kind: str,
    said: str,
    state: str,
    final: str,
    *,
    pull: dict[str, bool] | None = None,
) -> dict[str, object]:
    """Make a stop as a run records it: the stream of its session, the pull request then."""
    log = f"logs/{number:02d}-{kind}.jsonl"
    stop = {"kind": kind, "said": said, "log": log, "state": state, "final": final, "ended": True}
    return {**stop, "pull": pull}


STOPS: list[dict[str, object]] = [
    _stop(1, "need", "/surface-plan x", "interview", "Q?"),
    _stop(2, "answer", "A.", "awaiting-approval", "Read.", pull=CURRENT),
    _stop(3, "agreement", "Go.", "awaiting-approval", "No.", pull=CURRENT),
    _stop(4, "approval", "/surface-execute", "conformant", "Done.", pull=CURRENT),
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
    assert found["questions_handed_back"] == 0
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
    # The pull request: a draft at each hand over, described there, then by the stop of the loop.
    assert (found["pr_draft_at_hand_over"], found["pr_described"]) == (True, True)
    assert found["pr_refreshed"] is True
    assert (found["pr_marked_ready"], found["gh_not_played"]) == (False, 0)


def test_a_question_the_developer_hands_back_is_counted_among_the_questions(
    tmp_path: Path,
) -> None:
    stops = [
        _stop(1, "need", "/surface-plan x", "interview", "Q1?"),
        _stop(2, "answer", "C. At most 3 books.", "interview", "Q2?"),
        _stop(3, "answer", "That's your call, I take A.", "interview", "Q3?"),
        _stop(4, "answer", "A bad value is the assistant's call.", "awaiting-approval", "Read."),
        # Only an answer hands a question back: a correction that says the words is one still.
        _stop(5, "correction", "The order is your call, the limit is 3.", "awaiting-approval", "."),
    ]
    root = kept_run(tmp_path, journal=DRAFTED, outcome=STOPPED, stops=stops, stop_at_hand_over=True)
    found = measure(root, case(tmp_path))
    assert (found["questions"], found["questions_handed_back"]) == (3, 2)
    assert found["corrections"] == 1
    # Planning gives it: a run that stops at the hand over holds it like a run played whole.
    assert "questions_handed_back" not in EXECUTION
    assert "questions_handed_back" in GOALS


def _with_pulls(*pulls: dict[str, bool] | None) -> list[dict[str, object]]:
    """Give each stop of the run the pull request the harness found then."""
    return [{**stop, "pull": pull} for stop, pull in zip(STOPS, pulls, strict=True)]


def test_the_pull_request_steps_are_measured_from_the_stops_and_the_record(
    tmp_path: Path,
) -> None:
    stale = {"draft": True, "described": False}
    ready = {"draft": False, "described": True}
    # Opened one hand over late, then left by the loop with the description of the draft, by
    # sessions that asked to mark it ready and made a call the stand-in does not play.
    stops = _with_pulls(None, None, CURRENT, stale)
    late = kept_run(tmp_path / "late", journal=JOURNAL, stops=stops)
    project = late / "work" / "lending"
    toy.git(project, "init", "--quiet")
    assert gh(project, "pr", "ready") == 1
    assert gh(project, "api", "user") == 1
    found = measure(late, case(tmp_path))
    assert found["pr_draft_at_hand_over"] is False
    assert (found["pr_described"], found["pr_refreshed"]) == (True, False)
    assert (found["pr_marked_ready"], found["gh_not_played"]) == (True, 1)
    # Opened with another description than the one printed, and no draft at the next hand over.
    stops = _with_pulls(None, stale, ready, CURRENT)
    found = measure(kept_run(tmp_path / "other", journal=JOURNAL, stops=stops), case(tmp_path))
    assert found["pr_draft_at_hand_over"] is False
    assert (found["pr_described"], found["pr_refreshed"]) == (False, True)
    # A session killed at the timeout reached no stop: what it left is not the chain's refresh.
    stops = _with_pulls(None, CURRENT, CURRENT, stale)
    stops[-1]["ended"] = False
    found = measure(kept_run(tmp_path / "killed", journal=JOURNAL, stops=stops), case(tmp_path))
    assert (found["pr_described"], found["pr_refreshed"]) == (True, None)
    # Nor did a session that ends on a question while it drafts a revision: it pushed nothing.
    stops = _with_pulls(None, CURRENT, stale, CURRENT)
    stops[2]["state"] = "drafting"
    found = measure(kept_run(tmp_path / "asking", journal=JOURNAL, stops=stops), case(tmp_path))
    assert (found["pr_draft_at_hand_over"], found["pr_described"]) == (True, True)


def test_the_correction_a_case_expects_is_told_apart_and_left_out_of_the_corrections(
    tmp_path: Path,
) -> None:
    wrong_rule = ExpectedCorrection(why="The need says the wrong rule, on purpose.", says="7 days")
    expecting = case(tmp_path, expected_correction=wrong_rule)
    meant = "The rule is wrong: a member is reminded again only 7 Days or more after the last."
    other = "The command always exits 0."

    def found(name: str, *said: str, blueprints: tuple[str, ...] = (BLUEPRINT,)) -> list[object]:
        stops = [_stop(1, "need", "/surface-plan x", "awaiting-approval", "Read.")]
        stops += [
            _stop(number, "correction", text, "awaiting-approval", "Read.")
            for number, text in enumerate(said, start=2)
        ]
        root = kept_run(tmp_path / name, journal=DRAFTED, stops=stops, blueprints=blueprints)
        measures = measure(root, expecting)
        return [measures["corrections"], measures["expected_correction"]]

    # The blueprint sent back with the rule the developer meant is the one the case expects.
    assert found("caught", meant) == [0, True]
    # Any other blueprint sent back is a correction like those of every case.
    assert found("another-first", other, meant) == [1, True]
    assert found("another-alone", other) == [1, False]
    # It is left out once: sent back again, the amendment was not carried.
    assert found("twice", meant, meant) == [1, True]
    assert found("none") == [0, False]
    # A run that handed no blueprint over had nothing to send back: empty, never false.
    assert found("stuck", blueprints=()) == [0, None]
    # A case that expects none has no such measure, and counts every blueprint sent back.
    stops = [_stop(1, "correction", meant, "awaiting-approval", "Read.")]
    plain = measure(kept_run(tmp_path / "plain", journal=DRAFTED, stops=stops), case(tmp_path))
    assert [plain["corrections"], plain["expected_correction"]] == [1, None]
    # Planning gives both: a run that stops at the hand over holds them.
    assert "expected_correction" not in EXECUTION
    assert "expected_correction" in GOALS
    assert "expected_correction" not in DIRECTION


def test_the_report_knows_every_measure_of_the_pull_request(tmp_path: Path) -> None:
    found = measure(kept_run(tmp_path, journal=JOURNAL, stops=STOPS), case(tmp_path))
    measured = {name for name in found if name.startswith(("pr_", "gh_"))}
    assert measured == {
        "pr_draft_at_hand_over",
        "pr_described",
        "pr_refreshed",
        "pr_marked_ready",
        "gh_not_played",
    }
    # A measure the report does not name would leave its table without a word.
    assert measured <= set(GOALS)
    assert measured <= set(DIRECTION)


def test_a_run_that_opened_no_pull_request_has_no_description_to_measure(
    tmp_path: Path,
) -> None:
    stops = _with_pulls(None, None, None, None)
    found = measure(kept_run(tmp_path / "none", journal=JOURNAL, stops=stops), case(tmp_path))
    assert found["pr_draft_at_hand_over"] is False
    assert (found["pr_described"], found["pr_refreshed"]) == (None, None)
    assert found["pr_marked_ready"] is False
    # Stopped during the interview: no hand over to open a draft at.
    asked = kept_run(tmp_path / "asked", journal=JOURNAL[:1], stops=stops[:1])
    assert measure(asked, case(tmp_path))["pr_draft_at_hand_over"] is None


def test_a_run_kept_before_the_stand_in_has_no_measure_of_the_pull_request(
    tmp_path: Path,
) -> None:
    # Its stops kept nothing of a pull request: the image had no `gh` to open one with.
    stops = [{key: kept for key, kept in stop.items() if key != "pull"} for stop in STOPS]
    found = measure(kept_run(tmp_path, journal=JOURNAL, stops=stops), case(tmp_path))
    assert [name for name in found if name.startswith(("pr_", "gh_"))] == []
    assert found["conformant"] is True


def test_a_run_that_stops_at_the_hand_over_keeps_what_planning_gives_of_the_pull_request(
    tmp_path: Path,
) -> None:
    stopped = kept_run(
        tmp_path / "stopped",
        journal=DRAFTED,
        outcome=STOPPED,
        stops=PLANNED,
        stop_at_hand_over=True,
    )
    found = measure(stopped, case(tmp_path))
    # Planning opened the draft and described it: measured as in a run played whole.
    assert (found["pr_draft_at_hand_over"], found["pr_described"]) == (True, True)
    assert found["gh_not_played"] == 0
    assert not {"pr_draft_at_hand_over", "pr_described", "gh_not_played"} & set(EXECUTION)
    # The loop never ran: none of its stops refreshed anything, and "never marked ready" is a
    # promise to the end of the chain, which a False here would claim without having played it.
    assert (found["pr_refreshed"], found["pr_marked_ready"]) == (None, None)
    assert {"pr_refreshed", "pr_marked_ready"} <= set(EXECUTION)
    # A pull request that planning marked ready still shows: it is no draft at the hand over.
    ready = {"draft": False, "described": True}
    stops = [PLANNED[0], PLANNED[1], {**PLANNED[2], "pull": ready}]
    marked = kept_run(
        tmp_path / "marked", journal=DRAFTED, outcome=STOPPED, stops=stops, stop_at_hand_over=True
    )
    project = marked / "work" / "lending"
    toy.git(project, "init", "--quiet")
    assert gh(project, "pr", "ready") == 1
    found = measure(marked, case(tmp_path))
    assert (found["pr_draft_at_hand_over"], found["pr_marked_ready"]) == (False, None)


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
