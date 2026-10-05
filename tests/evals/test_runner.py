"""A run of a case, played without a session (evals/surface_evals/runner.py).

The sessions are replaced by a script that does through the real state script what a session of
the chain would have done, so the run drives a real journal: what is held here is the developer's
side, what is said and when, and what the run keeps.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import toy
from support import BLUEPRINT, PLAN, gh, stream

from surface_evals import developer, runner
from surface_evals.budget import Ledger
from surface_evals.corpus import load_cases
from surface_evals.runner import (
    AGREEMENT,
    EXECUTE,
    STOPPED,
    Run,
    build_project,
    plan_of,
    pr_body,
    pull_of,
    state_of,
    stops_at_hand_over,
)
from surface_evals.sessions import SessionLog, read_log

PLAN_FOLDER = "docs/plans/2026-01-15-overdue"
QUESTION = "Q1. How are ties ordered?"
ANSWER = "By book id."
CORRECTION = "A loan due today is not late: leave it out."


def _draft(project: Path) -> None:
    toy.record(project, PLAN_FOLDER, "interview-closed")
    toy.write(
        project,
        {
            f"{PLAN_FOLDER}/plan.md": PLAN,
            f"{PLAN_FOLDER}/blueprint.md": BLUEPRINT,
            f"{PLAN_FOLDER}/checks/rev-01-01.md": "omissions: 0\n",
        },
    )
    toy.record(
        project, PLAN_FOLDER, "check-done", "--report", "checks/rev-01-01.md", "--omissions", "0"
    )
    toy.record(project, PLAN_FOLDER, "plan-drafted")


def _build(project: Path) -> None:
    toy.record(project, PLAN_FOLDER, "plan-approved")
    toy.record(project, PLAN_FOLDER, "slice-done", "--slice", "1", "--gates", "unit tests")
    toy.gate(project, PLAN_FOLDER)
    toy.write(
        project,
        {
            f"{PLAN_FOLDER}/reviews/pass-01.md": "No finding.\n",
            f"{PLAN_FOLDER}/conformity.md": "1. Proved by the tests.\n",
        },
    )
    review = ("--report", "reviews/pass-01.md", "--defects", "0", "--deviations", "0")
    toy.record(project, PLAN_FOLDER, "review-done", *review, "--breaks", "0")
    toy.record(project, PLAN_FOLDER, "conformant", "--conformity", "conformity.md")


def _sessions(said: list[str]) -> Callable[..., SessionLog]:
    """Play the chain's side: open the plan, draft it once answered, build it once launched."""

    def run_chain(project: Path, prompt: str, log: Path, **_: object) -> SessionLog:
        said.append(prompt)
        if prompt.startswith("/surface-plan"):
            toy.write(project, {f"{PLAN_FOLDER}/specs.md": prompt})
            toy.record(project, PLAN_FOLDER, "plan-opened")
            return read_log(stream(log, session="plan", cost=0.1, final=QUESTION))
        if prompt == ANSWER:
            _draft(project)
            return read_log(stream(log, session="plan", cost=0.9, final="Read the blueprint."))
        if prompt == CORRECTION:
            toy.record(project, PLAN_FOLDER, "amendment-received")
            toy.write(
                project,
                {
                    f"{PLAN_FOLDER}/blueprint.md": BLUEPRINT.replace("past their due date", "late"),
                    f"{PLAN_FOLDER}/checks/rev-02-01.md": "omissions: 0\n",
                },
            )
            check = ("--report", "checks/rev-02-01.md", "--omissions", "0")
            toy.record(project, PLAN_FOLDER, "check-done", *check)
            toy.record(project, PLAN_FOLDER, "plan-drafted")
            return read_log(stream(log, session="plan", cost=1.4, final="Revision 2 is drafted."))
        if prompt == EXECUTE:
            _build(project)
            return read_log(stream(log, session="execute", cost=0.5, final="Conformant."))
        return read_log(stream(log, session="plan", cost=1.5, final="Only the launch approves."))

    return run_chain


def _developer(
    asked: list[str], read: list[str], corrections: list[str]
) -> tuple[Callable[..., SessionLog], Callable[..., SessionLog]]:
    """Play the developer: one answer to any question, then the corrections given, in order."""

    def answer(_case: object, question: str, log: Path, **_: object) -> SessionLog:
        asked.append(question)
        return read_log(stream(log, session="developer", cost=0.01, final=ANSWER))

    def read_blueprint(_case: object, blueprint: str, log: Path, **_: object) -> SessionLog:
        read.append(blueprint)
        said = corrections.pop(0) if corrections else "Nothing to change."
        return read_log(stream(log, session=f"reads-{len(read)}", cost=0.01, final=said))

    return answer, read_blueprint


@pytest.fixture
def played(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Run, list[str], list[str]]:
    said: list[str] = []
    asked: list[str] = []
    answer, read_blueprint = _developer(asked, [], [])
    monkeypatch.setattr(runner, "run_chain", _sessions(said))
    monkeypatch.setattr(runner, "answer", answer)
    monkeypatch.setattr(runner, "read_blueprint", read_blueprint)
    (case,) = [case for case in load_cases() if case.shape == "one-behavior"]
    ledger = Ledger.load(tmp_path, max_usd=None, max_points=None)
    run = Run(case=case, root=tmp_path / "run-01", ledger=ledger, developer_model=developer.MODEL)
    if run.plan():
        run.execute()
    run.close()
    return run, said, asked


def test_the_project_of_a_run_is_the_host_with_the_chain_installed(tmp_path: Path) -> None:
    project = build_project(tmp_path)
    assert (project / "lending" / "fines.py").is_file()
    assert (project / toy.STATE_SCRIPT).is_file()
    assert (project / ".claude" / "agents" / "surface-reviewer.md").is_file()
    assert toy.git(project, "status", "--porcelain").strip() == ""
    assert "origin/main" in toy.git(project, "branch", "--remotes")
    assert plan_of(project) is None
    assert state_of(project) is None


def test_a_run_plays_the_developer_from_the_need_to_the_launch(
    played: tuple[Run, list[str], list[str]],
) -> None:
    run, said, asked = played
    # The need, the answer of the developer to the question, a sentence that agrees, the launch.
    assert said[0] == f"/surface-plan {run.case.need}"
    assert said[1:] == [ANSWER, AGREEMENT, EXECUTE]
    assert asked == [QUESTION]
    assert [stop.kind for stop in run.stops] == ["need", "answer", "agreement", "approval"]
    assert [stop.state for stop in run.stops] == [
        "interview",
        "awaiting-approval",
        "awaiting-approval",
        "conformant",
    ]
    assert run.outcome == "conformant"
    assert run.approved_by_sentence is False
    # The planning session, resumed twice, the loop, one answer, one reading of the blueprint.
    assert run.ledger.usd == pytest.approx(1.5 + 0.5 + 0.01 + 0.01)


def test_a_run_keeps_what_was_said_the_blueprint_and_the_acceptance_of_the_code(
    played: tuple[Run, list[str], list[str]],
) -> None:
    run, _, _ = played
    record = json.loads((run.root / "run.json").read_text(encoding="utf-8"))
    assert record["case"] == run.case.name
    assert record["plan"] == PLAN_FOLDER
    assert record["stop_at_hand_over"] is False
    assert record["outcome"] == "conformant"
    assert record["blueprints"] == ["blueprint-rev-01.md"]
    assert (run.root / "blueprint-rev-01.md").read_text(encoding="utf-8") == BLUEPRINT
    assert record["stops"][0]["final"] == QUESTION
    assert (run.root / record["stops"][0]["log"]).is_file()
    # The script opened no pull request: every stop says so.
    assert [stop["pull"] for stop in record["stops"]] == [None] * 4
    assert (run.root / "logs" / "01-developer.jsonl").is_file()
    # The script built nothing: the acceptance tests ran on the host as it was, and say so.
    assert record["acceptance"]["ran"] > 0
    assert record["acceptance"]["failed"] > 0
    assert record["gate"] is True
    assert "conformant" in (run.root / "pr-body.md").read_text(encoding="utf-8")


def test_a_stop_tells_the_pull_request_of_the_branch_as_the_stand_in_keeps_it(
    tmp_path: Path,
) -> None:
    project = build_project(tmp_path)
    toy.git(project, "switch", "--quiet", "--create", "feat/overdue")
    toy.write(project, {f"{PLAN_FOLDER}/specs.md": "List the overdue loans.\n"})
    toy.record(project, PLAN_FOLDER, "plan-opened")
    _draft(project)
    toy.commit(project, "plan: list the overdue loans", [PLAN_FOLDER])
    toy.git(project, "push", "--quiet", "--set-upstream", "origin", "feat/overdue")
    assert pull_of(project) is None
    # A project a session left unreadable tells nothing, and its stop is kept all the same.
    assert pull_of(tmp_path / "gone") is None
    # What /surface-plan does at the first `plan-drafted`: a draft, with the description.
    opening = ("pr", "create", "--draft", "--title", "Overdue list", "--body-file", "-")
    assert gh(project, *opening, stdin=pr_body(project)) == 0
    assert pull_of(project) == {"draft": True, "described": True}
    # The plan moved on, and no stop refreshed the description yet.
    toy.record(project, PLAN_FOLDER, "plan-approved")
    assert pull_of(project) == {"draft": True, "described": False}
    # What every stop does, here with the trailing line break a command substitution drops.
    assert gh(project, "pr", "edit", "--body", pr_body(project).rstrip("\n")) == 0
    assert pull_of(project) == {"draft": True, "described": True}
    # What the chain never does.
    assert gh(project, "pr", "ready") == 0
    assert pull_of(project) == {"draft": False, "described": True}


def test_a_blueprint_the_developer_corrects_is_drawn_again_before_the_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    said: list[str] = []
    read: list[str] = []
    answer, read_blueprint = _developer([], read, [CORRECTION])
    monkeypatch.setattr(runner, "run_chain", _sessions(said))
    monkeypatch.setattr(runner, "answer", answer)
    monkeypatch.setattr(runner, "read_blueprint", read_blueprint)
    (case,) = [case for case in load_cases() if case.shape == "one-behavior"]
    ledger = Ledger.load(tmp_path, max_usd=None, max_points=None)
    run = Run(case=case, root=tmp_path / "run-01", ledger=ledger, developer_model="sonnet")
    assert run.plan() is True
    # The developer read revision 1, sent it back, read revision 2 and had nothing to change.
    assert said[1:] == [ANSWER, CORRECTION, AGREEMENT]
    assert [stop.kind for stop in run.stops] == ["need", "answer", "correction", "agreement"]
    assert run.blueprints == ["blueprint-rev-01.md", "blueprint-rev-02.md"]
    assert read[0] == BLUEPRINT
    assert "late" in read[1]
    assert len(read) == 2
    assert run.approved_by_sentence is False


def test_a_run_that_stops_at_the_hand_over_plays_planning_and_launches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    said: list[str] = []
    read: list[str] = []
    answer, read_blueprint = _developer([], read, [CORRECTION])
    monkeypatch.setattr(runner, "run_chain", _sessions(said))
    monkeypatch.setattr(runner, "answer", answer)
    monkeypatch.setattr(runner, "read_blueprint", read_blueprint)
    (case,) = [case for case in load_cases() if case.shape == "one-behavior"]
    ledger = Ledger.load(tmp_path, max_usd=None, max_points=None)
    run = Run(
        case=case,
        root=tmp_path / "run-01",
        ledger=ledger,
        developer_model="sonnet",
        stop_at_hand_over=True,
    )
    if run.plan():
        run.execute()
    run.close()
    # Planning as in a run played whole: the answer, the blueprint read and sent back, the
    # sentence that agrees. Then nothing: no launch.
    assert said[1:] == [ANSWER, CORRECTION, AGREEMENT]
    assert [stop.kind for stop in run.stops] == ["need", "answer", "correction", "agreement"]
    assert len(read) == 2
    assert run.outcome == STOPPED
    assert run.approved_by_sentence is False
    assert state_of(run.project) == "awaiting-approval"
    # The ledger counts what was played: the planning session, one answer, two readings.
    assert run.ledger.usd == pytest.approx(1.5 + 0.01 + 0.02)
    record = json.loads((run.root / "run.json").read_text(encoding="utf-8"))
    assert record["stop_at_hand_over"] is True
    assert stops_at_hand_over(run.root) is True
    assert record["outcome"] == STOPPED
    assert record["blueprints"] == ["blueprint-rev-01.md", "blueprint-rev-02.md"]
    # Nothing was built: no test ran, and the record holds no result of one.
    assert record["acceptance"] is None
    assert record["gate"] is None
    assert "awaiting-approval" in (run.root / "pr-body.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("stop_at_hand_over", [False, True])
def test_a_run_stops_at_the_ceiling_before_it_starts_a_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, stop_at_hand_over: bool
) -> None:
    said: list[str] = []
    monkeypatch.setattr(runner, "run_chain", _sessions(said))
    (case,) = [case for case in load_cases() if case.shape == "one-behavior"]
    ledger = Ledger.load(tmp_path, max_usd=1.0, max_points=None)
    ledger.note(read_log(stream(tmp_path / "earlier.jsonl", cost=2.0)))
    run = Run(
        case=case,
        root=tmp_path / "run-01",
        ledger=ledger,
        developer_model="sonnet",
        stop_at_hand_over=stop_at_hand_over,
    )
    assert run.plan() is False
    assert said == []
    assert run.outcome == "budget"
