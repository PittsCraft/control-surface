"""The JSON output has the documented shape: golden files, every one with `"v": 1`.

The contract is in ARCHITECTURE.md, Command line contract.
"""

from pathlib import Path

import pytest
from cli_support import PLAN, Project, assert_golden


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path)


def test_golden_list(project: Project) -> None:
    project.reach("awaiting-approval", "2026-09-01-first")
    project.reach("conform", "2026-09-02-second")
    assert_golden("list.json", project.run().out)


def test_golden_list_with_an_unreadable_journal(project: Project) -> None:
    project.reach("executing", "2026-09-01-good")
    bad = project.reach("executing", "2026-09-02-bad")
    (bad / "journal.jsonl").write_text("not json\n", encoding="utf-8")
    assert_golden("list-unreadable.json", project.run().out)


def test_golden_show_executing(project: Project) -> None:
    project.reach("executing", gates=("make test", "make lint"))
    project.record(PLAN, "slice-done", "--slice", "1", "--gates", "lint")
    assert_golden("show-executing.json", project.run("show", PLAN).out)


def test_golden_show_with_a_suspected_break(project: Project) -> None:
    project.reach("executing")
    project.record(PLAN, "break-suspected", "--slice", "1", "--why", "the overview names no id")
    assert_golden("show-suspected.json", project.run("show", PLAN).out)


def test_golden_show_without_events(project: Project) -> None:
    (project.plan() / "journal.jsonl").write_text("", encoding="utf-8")
    assert_golden("show-empty.json", project.run("show", PLAN).out)


def test_golden_record_accepted(project: Project) -> None:
    project.reach("executing")
    result = project.record(PLAN, "slice-done", "--slice", "1", "--gates", "lint")
    assert_golden("record-accepted.json", result.out)


def test_golden_record_refused(project: Project) -> None:
    project.reach("executing")
    result = project.record(PLAN, "slice-done", "--slice", "9", "--gates", "lint")
    assert_golden("record-refused.json", result.out)


def test_golden_abandon(project: Project) -> None:
    project.reach("executing")
    assert_golden("abandon.json", project.run("abandon", PLAN, "--why", "changed course").out)


def test_golden_usage_error(project: Project) -> None:
    project.reach("reviewing")
    assert_golden("error.json", project.record(PLAN, "gates-run", "--result", "pass").out)


def test_golden_check_passing(project: Project) -> None:
    project.reach("conform", "2026-09-01-done")
    project.reach("awaiting-approval", "2026-09-02-dropped")
    project.run("abandon", "2026-09-02-dropped", "--why", "not wanted")
    assert_golden("check-passed.json", project.run("check", "--require", "conform").out)


def test_golden_check_failing(project: Project) -> None:
    project.reach("executing", "2026-09-01-running")
    project.reach("executing", "2026-09-02-dropped")
    project.run("abandon", "2026-09-02-dropped", "--why", "changed course")
    edited = project.reach("conform", "2026-09-03-edited")
    (edited / "overview.md").write_text("# Overview\nedited\n", encoding="utf-8")
    assert_golden("check-failed.json", project.run("check", "--require", "conform").out)


def test_golden_check_without_requirement(project: Project) -> None:
    project.reach("executing")
    assert_golden("check-plain.json", project.run("check").out)


def test_every_answer_carries_the_version(project: Project) -> None:
    project.reach("executing")
    answers = [
        project.run(),
        project.run("show", PLAN),
        project.run("check"),
        project.run("check", "--require", "conform"),
        project.record(PLAN, "slice-done", "--slice", "1", "--gates", "lint"),
        project.record(PLAN, "slice-done", "--slice", "1", "--gates", "lint"),
        project.record(PLAN, "nonsense"),
        project.run("show", "missing"),
    ]
    assert [answer.json()["v"] for answer in answers] == [1] * len(answers)
