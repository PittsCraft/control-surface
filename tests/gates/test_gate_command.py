"""`gate`: the declared command runs, its exit code is what the journal keeps (ADR 0017)."""

from pathlib import Path

import pytest
from cli_support import FIXED_NOW, PLAN, Project
from gates_support import SHORT_MINUTE, declare, events, reviewing, run_report

from surface_status import gates
from surface_status.events import GateResult


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path)


def test_a_passing_command_is_recorded_green_and_leaves_the_state_alone(project: Project) -> None:
    reviewing(project, "true")
    result = project.run("gate", PLAN)
    assert result.code == 0
    answer = result.json()
    assert answer.pop("duration_seconds") >= 0
    assert answer == {
        "v": 1,
        "ok": True,
        "plan": PLAN,
        "ran": True,
        "run": 1,
        "result": "pass",
        "exit_code": 0,
        "report": "gates/run-01.txt",
        "at": "2026-09-29T09:00:00Z",
        "state": "reviewing",
    }
    assert events(project)[-1] == {
        "v": 1,
        "at": "2026-09-29T09:00:00Z",
        "event": "gates-run",
        "run": 1,
        "result": "pass",
    }


def test_the_report_holds_the_command_the_exit_code_the_duration_and_the_output(
    project: Project,
) -> None:
    reviewing(project, "echo to-stdout; echo to-stderr >&2; exit 3")
    project.run("gate", PLAN)
    lines = run_report(project).splitlines()
    assert lines[0] == "command: echo to-stdout; echo to-stderr >&2; exit 3"
    assert lines[1] == "result: fail"
    assert lines[2] == "exit code: 3"
    assert lines[3].startswith("duration: ")
    assert lines[3].endswith(" seconds")
    assert "to-stdout" in lines
    assert "to-stderr" in lines


def test_the_report_keeps_only_the_end_of_a_long_output(project: Project) -> None:
    reviewing(project, "seq 1 500")
    project.run("gate", PLAN)
    lines = run_report(project).splitlines()
    assert lines[-1] == "500"
    assert "301" in lines
    assert "300" not in lines
    assert "1" not in lines


def test_runs_are_numbered_one_after_the_other(project: Project) -> None:
    reviewing(project, "true")
    project.run("gate", PLAN)
    project.run("gate", PLAN)
    assert [line["run"] for line in events(project) if line["event"] == "gates-run"] == [1, 2]
    assert (project.plans / PLAN / "gates" / "run-02.txt").is_file()


def test_the_command_runs_at_the_project_root_through_the_shell(project: Project) -> None:
    reviewing(project, "cd . && pwd -P")
    project.run("gate", PLAN)
    assert str(project.root.resolve()) in run_report(project).splitlines()


def test_a_command_killed_by_a_signal_is_a_failure(project: Project) -> None:
    reviewing(project, "kill -9 $$")
    result = project.run("gate", PLAN)
    assert result.code == 1
    assert result.json()["result"] == "fail"
    assert "exit code: -9 (killed by signal 9)" in run_report(project)


def test_a_timeout_is_recorded_as_a_timeout_and_reported_as_a_failure(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gates, "SECONDS_PER_MINUTE", SHORT_MINUTE)
    reviewing(project, "echo started; sleep 30", gate_timeout_minutes=1)
    result = project.run("gate", PLAN)
    assert result.code == 1
    answer = result.json()
    assert answer["result"] == "timeout"
    assert answer["exit_code"] is None
    assert answer["duration_seconds"] < 10
    assert answer["state"] == "fixing"
    assert events(project)[-1]["result"] == "timeout"
    report = run_report(project)
    assert "result: timeout" in report
    assert "exit code: none (killed after the timeout of 0.3 seconds)" in report
    assert "started" in report.splitlines()


def test_the_timeout_defaults_to_the_setting_in_minutes(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[float] = []

    def fake(_command: str, _cwd: Path, timeout_seconds: float) -> gates.Execution:
        seen.append(timeout_seconds)
        return gates.Execution(GateResult.PASS, 0, 0.0, "")

    monkeypatch.setattr(gates, "execute", fake)
    reviewing(project, "true", gate_timeout_minutes=7)
    project.run("gate", PLAN)
    assert seen == [7 * 60]


def test_the_text_output_names_the_run_and_the_state(project: Project) -> None:
    reviewing(project, "true")
    ok = project.run("gate", PLAN, as_json=False)
    assert ok.code == 0
    assert ok.out.startswith(f"gates pass for {PLAN} (run 1, ")
    assert ok.out.endswith("): gates/run-01.txt; state reviewing\n")
    declare(project, "false")
    failed = project.run("gate", PLAN, as_json=False)
    assert failed.code == 1
    assert failed.out == ""
    assert failed.err.endswith("): gates/run-02.txt; state fixing\n")


def test_gate_needs_a_plan(project: Project) -> None:
    result = project.run("gate")
    assert result.code == 2


def test_an_unknown_plan_is_a_usage_error(project: Project) -> None:
    reviewing(project, "true")
    result = project.run("gate", "no-such-plan")
    assert result.code == 2
    assert result.json()["ok"] is False


def test_the_run_is_recorded_at_the_time_of_the_clock(project: Project) -> None:
    reviewing(project, "true")
    project.run("gate", PLAN)
    assert events(project)[-1]["at"] == FIXED_NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
