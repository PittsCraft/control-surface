"""The plan list and `show`: state, whose turn it is, next step, slices, passes, settings."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from cli_support import PLAN, Project, plan_text

from surface_status.events import PlanOpened
from surface_status.machine import State, apply
from surface_status.report import turn_of


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path)


def test_no_argument_lists_the_plans_with_state_and_hand(project: Project) -> None:
    project.reach("interview", "2026-09-01-a")
    project.reach("executing", "2026-09-02-b")
    project.reach("conformant", "2026-09-03-c")
    assert project.run().json()["plans"] == [
        {"name": "2026-09-01-a", "state": "interview", "turn": "developer"},
        {"name": "2026-09-02-b", "state": "executing", "turn": "agents"},
        {"name": "2026-09-03-c", "state": "conformant", "turn": "nobody"},
    ]


def test_the_text_list_has_one_row_per_plan(project: Project) -> None:
    project.reach("awaiting-approval")
    text = project.run(as_json=False).out
    assert [row.split() for row in text.splitlines()] == [
        [PLAN, "awaiting-approval", "turn:", "developer"]
    ]


def test_an_empty_project_lists_no_plan(project: Project) -> None:
    assert project.run().json() == {"v": 1, "plans": []}
    assert project.run(as_json=False).out == "no plan\n"


def test_the_list_reports_an_unreadable_journal_and_exits_2(project: Project) -> None:
    project.reach("executing", "2026-09-01-good")
    bad = project.reach("executing", "2026-09-02-bad")
    (bad / "journal.jsonl").write_text("not json\n", encoding="utf-8")
    result = project.run()
    assert result.code == 2
    rows = result.json()["plans"]
    assert rows[0]["state"] == "executing"
    assert rows[1]["state"] is None
    assert "line 1" in rows[1]["error"]


def test_the_hand_follows_the_table_of_the_specs() -> None:
    developer = {
        State.INTERVIEW,
        State.AWAITING_APPROVAL,
        State.PLAN_CHANGE_PROPOSED,
        State.BLOCKED,
    }
    for state in State:
        if state in {State.CONFORMANT, State.ABANDONED}:
            expected = "nobody"
        else:
            expected = "developer" if state in developer else "agents"
        assert _hand(state) == expected


def _hand(state: State) -> str:
    opened = apply(None, PlanOpened(slug="x"))
    return turn_of(replace(opened, state=state))


def test_show_reports_the_slices_and_the_counters(project: Project) -> None:
    project.reach("reviewing")
    shown = project.run("show", PLAN).json()
    assert shown["state"] == "reviewing"
    assert shown["slices"] == {"declared": [1, 2], "done": [1, 2], "remaining": []}
    assert shown["passes"] == {"planning": 0, "execution": 0, "ceiling": 3}
    assert shown["last_event"] == "slice-done"


def test_show_names_the_slice_the_executor_launches_next(project: Project) -> None:
    project.reach("executing")
    project.record(PLAN, "slice-done", "--slice", "2", "--gates", "lint")
    shown = project.run("show", PLAN).json()
    assert shown["slices"]["remaining"] == [1]
    assert shown["next_step"] == "surface-execute: launch slice 1"


def test_show_counts_the_passes_of_the_loop(project: Project) -> None:
    project.reach("reviewing")
    project.record(
        PLAN, "review-done", "--report", "reviews/pass-01.md",
        "--defects", "1", "--deviations", "0", "--breaks", "0",
    )  # fmt: skip
    shown = project.run("show", PLAN).json()
    assert shown["state"] == "fixing"
    assert shown["passes"]["execution"] == 1


def test_show_prints_the_effective_settings(project: Project) -> None:
    project.reach("interview")
    settings = project.run("show", PLAN).json()["settings"]
    assert settings["plans_dir"] == "docs/plans"
    assert settings["max_autonomous_passes"] == 3
    assert settings["models"] == {
        "extractor": "opus",
        "checker": "opus",
        "executor": "sonnet",
        "reviewer": "opus",
    }
    (project.root / ".claude").mkdir()
    (project.root / ".claude" / "surface.json").write_text(
        json.dumps({"max_autonomous_passes": 5, "models": {"executor": "opus"}}), encoding="utf-8"
    )
    changed = project.run("show", PLAN).json()
    assert changed["settings"]["max_autonomous_passes"] == 5
    assert changed["settings"]["models"]["executor"] == "opus"
    assert changed["passes"]["ceiling"] == 5


def test_show_names_the_gates_of_the_drafted_revision(project: Project) -> None:
    project.reach("drafting")
    assert project.run("show", PLAN).json()["gates"] is None
    assert "gates: not named by a drafted revision" in project.run("show", PLAN, as_json=False).out
    folder = project.plans / PLAN
    folder.joinpath("plan.md").write_text(plan_text(("make test", "make lint")), encoding="utf-8")
    project.record(PLAN, "check-done", "--report", "checks/rev-01-01.md", "--omissions", "0")
    assert project.record(PLAN, "plan-drafted").code == 0
    assert project.run("show", PLAN).json()["gates"] == ["make test", "make lint"]
    text = project.run("show", PLAN, as_json=False).out
    assert "gates: make test; make lint" in text


def test_a_plan_without_its_gates_block_is_not_drafted(project: Project) -> None:
    project.reach("drafting")
    (project.plans / PLAN / "plan.md").write_text("<!-- slice:1 -->\n", encoding="utf-8")
    project.record(PLAN, "check-done", "--report", "checks/rev-01-01.md", "--omissions", "0")
    refused = project.record(PLAN, "plan-drafted")
    assert refused.code == 1
    assert refused.json()["refused"]["code"] == "gate-list"


def test_a_removed_setting_is_a_usage_error_that_names_its_replacement(project: Project) -> None:
    (project.root / ".claude").mkdir()
    (project.root / ".claude" / "surface.json").write_text(
        '{"gate_command": "make check"}', encoding="utf-8"
    )
    result = project.run()
    assert result.code == 2
    error = result.json()["error"]
    assert "'gate_command' is gone" in error
    assert "the approved plan names" in error


def test_the_plans_dir_setting_moves_the_search(project: Project) -> None:
    (project.root / ".claude").mkdir()
    (project.root / ".claude" / "surface.json").write_text(
        json.dumps({"plans_dir": "work/plans"}), encoding="utf-8"
    )
    other = project.root / "work" / "plans" / "2026-09-05-elsewhere"
    other.mkdir(parents=True)
    (other / "blueprint.md").write_text("# Blueprint\n", encoding="utf-8")
    (other / "plan.md").write_text("<!-- slice:1 -->\n", encoding="utf-8")
    assert project.run("record", "2026-09-05-elsewhere", "plan-opened").code == 0
    assert [plan["name"] for plan in project.run().json()["plans"]] == ["2026-09-05-elsewhere"]


def test_a_settings_file_that_does_not_parse_is_a_usage_error(project: Project) -> None:
    (project.root / ".claude").mkdir()
    (project.root / ".claude" / "surface.json").write_text('{"max_pases": 2}', encoding="utf-8")
    result = project.run()
    assert result.code == 2
    assert "max_autonomous_passes" in result.json()["error"]


def test_show_of_a_journal_without_events_says_the_plan_is_not_opened(project: Project) -> None:
    folder = project.plan()
    (folder / "journal.jsonl").write_text("", encoding="utf-8")
    shown = project.run("show", PLAN).json()
    assert shown["state"] is None
    assert shown["last_event"] is None
    assert "plan-opened" in shown["next_step"]


def _block(project: Project) -> None:
    assert project.record(PLAN, "blocked", "--why", "does not converge").code == 0


def _propose(project: Project) -> None:
    args = ("--proposal", "plan-changes/01.md", "--slice", "1")
    assert project.record(PLAN, "plan-change-proposed", *args).code == 0


def _defect(project: Project) -> None:
    args = (
        "--report",
        "reviews/pass-01.md",
        "--defects",
        "1",
        "--deviations",
        "0",
        "--breaks",
        "0",
    )
    assert project.record(PLAN, "review-done", *args).code == 0


# Each state an approval binds, as the way there and a last step from it.
BOUND = {
    "executing": ("executing", None),
    "reviewing": ("reviewing", None),
    "fixing": ("reviewing", _defect),
    "conformant": ("conformant", None),
    "blocked during execution": ("executing", _block),
    "plan-change-proposed": ("plan-change-proposed", None),
}


@pytest.mark.parametrize("bound", list(BOUND))
def test_show_raises_an_alarm_on_an_blueprint_edited_since_its_approval(
    project: Project, bound: str
) -> None:
    reached, then = BOUND[bound]
    folder = project.reach(reached)
    if then is not None:
        then(project)
    assert project.run("show", PLAN).json()["alarms"] == []
    (folder / "blueprint.md").write_text("# Blueprint\nedited\n", encoding="utf-8")
    alarms = project.run("show", PLAN).json()["alarms"]
    assert [alarm["code"] for alarm in alarms] == ["blueprint-changed"]
    text = project.run("show", PLAN, as_json=False).out
    assert "ALARM blueprint-changed: blueprint.md differs" in text


def test_show_raises_an_alarm_on_an_approved_blueprint_deleted(project: Project) -> None:
    folder = project.reach("reviewing")
    (folder / "blueprint.md").unlink()
    alarms = project.run("show", PLAN).json()["alarms"]
    assert [alarm["code"] for alarm in alarms] == ["blueprint-missing"]


@pytest.mark.parametrize("unbound", ["drafting", "awaiting-approval", "blocked during planning"])
def test_show_raises_no_alarm_while_no_approval_binds(project: Project, unbound: str) -> None:
    folder = project.reach("drafting" if unbound == "blocked during planning" else unbound)
    if unbound == "blocked during planning":
        _block(project)
    (folder / "blueprint.md").write_text("# Blueprint\nedited\n", encoding="utf-8")
    assert project.run("show", PLAN).json()["alarms"] == []
    assert "ALARM" not in project.run("show", PLAN, as_json=False).out


def test_an_amendment_releases_the_blueprint_from_the_last_approval(project: Project) -> None:
    folder = project.reach("executing")
    _block(project)
    assert project.record(PLAN, "amendment-received").code == 0
    (folder / "blueprint.md").write_text("# Blueprint\nrevision 2\n", encoding="utf-8")
    assert project.run("show", PLAN).json()["alarms"] == []


def test_the_text_of_show_holds_what_the_json_holds(project: Project) -> None:
    project.reach("reviewing")
    text = project.run("show", PLAN, as_json=False).out
    assert f"plan: {PLAN}" in text
    assert "state: reviewing (turn: agents)" in text
    assert "slices: done 1, 2; remaining none" in text
    assert "passes: planning 0, execution 0, ceiling 3" in text
    assert "gates: none" in text
    assert "max_autonomous_passes: 3" in text


REASON = "the export needs a column the blueprint does not show"


def test_a_suspected_break_waits_in_the_journal_for_a_later_session(project: Project) -> None:
    """The executor records its reason; a session launched after it reads it from `show`."""
    folder = project.reach("executing")
    suspected = project.record(PLAN, "break-suspected", "--slice", "1", "--why", REASON)
    assert suspected.code == 0
    assert suspected.json()["state"] == "executing"
    shown = project.run("show", PLAN).json()
    assert shown["pending_suspicion"] == {"slice": 1, "why": REASON}
    assert shown["next_step"] == (
        "surface-execute: a reviewer judges the break suspected during slice 1"
    )
    assert f"suspected break: slice 1: {REASON}" in project.run("show", PLAN, as_json=False).out
    before = project.journal()
    refused = project.record(PLAN, "slice-done", "--slice", "1", "--gates", "lint")
    assert refused.code == 1
    assert refused.json()["refused"]["code"] == "suspicion"
    assert project.journal() == before
    note = folder / "reviews" / "suspicion-01.md"
    note.parent.mkdir(exist_ok=True)
    note.write_text("no break\n", encoding="utf-8")
    args = ("--slice", "1", "--report", "reviews/suspicion-01.md")
    assert project.record(PLAN, "suspicion-dismissed", *args).code == 0
    assert project.run("show", PLAN).json()["pending_suspicion"] is None
    assert project.record(PLAN, "slice-done", "--slice", "1", "--gates", "lint").code == 0


def test_a_confirmed_suspicion_is_no_longer_pending(project: Project) -> None:
    project.reach("executing")
    assert project.record(PLAN, "break-suspected", "--slice", "1", "--why", REASON).code == 0
    _propose(project)
    shown = project.run("show", PLAN).json()
    assert shown["state"] == "plan-change-proposed"
    assert shown["pending_suspicion"] is None
    assert shown["pending_proposal"] == "plan-changes/01.md"
