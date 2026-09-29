"""The gate runner: the review guard, the failed pass, the process group, the ceiling."""

from pathlib import Path

import pytest
from cli_support import PLAN, Project
from gates_support import SHORT_MINUTE, events, reviewing, wait_gone

from surface_status import gates

REVIEW = (
    "--report",
    "reviews/pass-01.md",
    "--defects",
    "0",
    "--deviations",
    "0",
    "--breaks",
    "0",
)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path)


def _execution_passes(project: Project) -> int:
    passes: int = project.run("show", PLAN).json()["passes"]["execution"]
    return passes


def test_a_review_is_refused_without_a_green_gate_run_since_the_last_change(
    project: Project,
) -> None:
    reviewing(project, "true")
    before = project.journal()
    refused = project.record(PLAN, "review-done", *REVIEW)
    assert refused.code == 1
    assert refused.json()["refused"]["code"] == "gates"
    assert project.journal() == before
    assert project.run("gate", PLAN).code == 0
    assert project.record(PLAN, "review-done", *REVIEW).code == 0


def test_a_green_run_does_not_carry_over_to_a_second_review(project: Project) -> None:
    reviewing(project, "true")
    project.run("gate", PLAN)
    assert project.record(PLAN, "review-done", *REVIEW).code == 0
    again = project.record(PLAN, "review-done", *REVIEW)
    assert again.json()["refused"]["code"] == "gates"


def test_a_failed_run_counts_as_a_pass_and_moves_reviewing_to_fixing(project: Project) -> None:
    reviewing(project, "false")
    assert _execution_passes(project) == 0
    result = project.run("gate", PLAN)
    assert result.code == 1
    assert result.json()["state"] == "fixing"
    assert project.run("show", PLAN).json()["state"] == "fixing"
    assert _execution_passes(project) == 1
    assert events(project)[-1]["result"] == "fail"


def test_a_green_run_is_not_a_pass(project: Project) -> None:
    reviewing(project, "true")
    project.run("gate", PLAN)
    assert _execution_passes(project) == 0


def test_a_fix_is_recorded_after_a_green_run_and_not_after_a_failed_one(
    project: Project, tmp_path: Path
) -> None:
    fixed = tmp_path / "fixed"
    reviewing(project, f"test -e {fixed}")
    project.run("gate", PLAN)
    assert project.record(PLAN, "fix-done").json()["refused"]["code"] == "gates"
    fixed.touch()
    project.run("gate", PLAN)
    assert project.record(PLAN, "fix-done").code == 0


def test_a_timeout_leaves_no_child_process_behind(
    project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gates, "SECONDS_PER_MINUTE", SHORT_MINUTE)
    monkeypatch.setattr(gates, "TIMEOUT_MINUTES", 1)
    pids = tmp_path / "pids"
    command = f"sleep 60 & echo $! >> {pids}; sh -c 'sleep 60 & echo $! >> {pids}; wait' & wait"
    reviewing(project, command)
    result = project.run("gate", PLAN)
    assert result.json()["result"] == "timeout"
    found = [int(line) for line in pids.read_text(encoding="utf-8").split()]
    assert len(found) == 2
    assert all(wait_gone(pid) for pid in found)


def test_a_child_left_behind_by_a_command_that_finished_is_killed_too(
    project: Project, tmp_path: Path
) -> None:
    pids = tmp_path / "pids"
    reviewing(project, f"sleep 60 & echo $! > {pids}")
    result = project.run("gate", PLAN)
    assert result.json()["result"] == "pass"
    assert wait_gone(int(pids.read_text(encoding="utf-8")))


def test_the_gate_refuses_to_start_at_the_ceiling(project: Project, tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    reviewing(project, f"touch {marker}; false", max_autonomous_passes=1)
    assert project.run("gate", PLAN).code == 1
    assert _execution_passes(project) == 1
    marker.unlink()
    before = project.journal()
    refused = project.run("gate", PLAN)
    assert refused.code == 1
    assert refused.json() == {
        "v": 1,
        "ok": False,
        "plan": PLAN,
        "event": "gates-run",
        "refused": {
            "code": "ceiling",
            "reason": "1 autonomous passes reached the ceiling of 1",
        },
    }
    assert not marker.exists()
    assert project.journal() == before
    assert not (project.plans / PLAN / "gates" / "run-02.txt").exists()


def test_a_green_command_is_not_run_at_the_ceiling_either(project: Project, tmp_path: Path) -> None:
    marker, green = tmp_path / "marker", tmp_path / "green"
    reviewing(project, f"touch {marker}; test -e {green}", max_autonomous_passes=1)
    project.run("gate", PLAN)
    marker.unlink()
    green.touch()
    assert project.run("gate", PLAN).code == 1
    assert not marker.exists()


def test_the_gate_is_refused_before_it_runs_when_the_state_takes_no_gate_run(
    project: Project, tmp_path: Path
) -> None:
    marker = tmp_path / "marker"
    project.reach("executing", gates=(f"touch {marker}",))
    refused = project.run("gate", PLAN)
    assert refused.code == 1
    assert refused.json()["refused"]["code"] == "transition"
    assert not marker.exists()
    assert not (project.plans / PLAN / "gates").exists()


def test_when_the_plan_names_no_gate_gate_says_so_and_the_gate_guards_are_lifted(
    project: Project,
) -> None:
    reviewing(project)
    before = project.journal()
    result = project.run("gate", PLAN)
    assert result.code == 0
    answer = result.json()
    assert answer["ran"] is False
    assert answer["reason"].startswith("the approved plan names no gate command")
    assert project.journal() == before
    assert not (project.plans / PLAN / "gates").exists()
    assert project.record(PLAN, "review-done", *REVIEW).code == 0


def test_the_text_answer_without_a_command_says_so(project: Project) -> None:
    reviewing(project)
    result = project.run("gate", PLAN, as_json=False)
    assert result.code == 0
    assert result.out.startswith("the approved plan names no gate command")
