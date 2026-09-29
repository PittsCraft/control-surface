"""`gate`: the commands of the approved plan run, their exit codes are what the journal keeps."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from cli_support import FIXED_NOW, PLAN, Project, plan_text
from gates_support import SHORT_MINUTE, events, reviewing, run_report

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
    assert answer.pop("commands")[0].pop("duration_seconds") >= 0
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
    assert lines[0] == "result: fail"
    assert lines[1].startswith("duration: ")
    assert lines[2] == "timeout: 1800 seconds for the whole run"
    assert lines[3] == "commands: 1, in order, stopping at the first that fails"
    assert lines[5] == "command 1: echo to-stdout; echo to-stderr >&2; exit 3"
    assert lines[6] == "result: fail"
    assert lines[7] == "exit code: 3"
    assert lines[8].startswith("duration: ")
    assert lines[8].endswith(" seconds")
    assert "to-stdout" in lines
    assert "to-stderr" in lines


def test_the_commands_run_in_order_and_stop_at_the_first_failure(
    project: Project, tmp_path: Path
) -> None:
    trace = tmp_path / "trace"
    reviewing(project, f"echo one >> {trace}", f"echo two >> {trace}; exit 4", f"echo 3 >> {trace}")
    result = project.run("gate", PLAN)
    assert result.code == 1
    answer = result.json()
    assert answer["result"] == "fail"
    assert answer["exit_code"] == 4
    assert [(step["result"], step["exit_code"]) for step in answer["commands"]] == [
        ("pass", 0),
        ("fail", 4),
    ]
    assert trace.read_text(encoding="utf-8") == "one\ntwo\n"
    report = run_report(project)
    assert "commands: 3, in order, stopping at the first that fails" in report
    assert report.endswith(f"command 3: echo 3 >> {trace}\nnot run: an earlier command failed\n")
    assert [line["result"] for line in events(project) if line["event"] == "gates-run"] == ["fail"]


def test_the_run_is_green_when_every_command_passes(project: Project) -> None:
    reviewing(project, "true", "echo second")
    result = project.run("gate", PLAN)
    assert result.code == 0
    assert [step["command"] for step in result.json()["commands"]] == ["true", "echo second"]
    assert "command 2: echo second" in run_report(project)


def test_the_gates_are_those_of_the_approved_revision_not_of_a_later_edit(
    project: Project,
) -> None:
    folder = reviewing(project, "true")
    (folder / "plan.md").write_text(plan_text(("false",)), encoding="utf-8")
    result = project.run("gate", PLAN)
    assert result.code == 0
    assert "command 1: true" in run_report(project)


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
    monkeypatch.setattr(gates, "TIMEOUT_MINUTES", 1)
    reviewing(project, "echo started; sleep 30")
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
    assert "exit code: none (killed: the run reached its timeout of 0.3 seconds)" in report
    assert "started" in report.splitlines()


def test_the_timeout_is_thirty_minutes_for_the_whole_run(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]
    seen: list[float] = []

    def fake(_command: str, _cwd: Path, timeout_seconds: float) -> gates.Execution:
        seen.append(timeout_seconds)
        clock[0] += 700.0
        return gates.Execution(GateResult.PASS, 0, 700.0, "")

    monkeypatch.setattr(gates, "execute", fake)
    monkeypatch.setattr(gates, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    reviewing(project, "one", "two", "three", "four")
    result = project.run("gate", PLAN)
    assert seen == [1800.0, 1100.0, 400.0]
    answer = result.json()
    assert answer["result"] == "timeout"
    assert answer["commands"][-1] == {
        "command": "four",
        "result": "timeout",
        "exit_code": None,
        "duration_seconds": 0.0,
    }


def test_the_text_output_names_the_run_and_the_state(project: Project, tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    reviewing(project, f"test ! -e {broken}")
    ok = project.run("gate", PLAN, as_json=False)
    assert ok.code == 0
    assert ok.out.startswith(f"gates pass for {PLAN} (run 1, ")
    assert ok.out.endswith("): gates/run-01.txt; state reviewing\n")
    broken.touch()
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
