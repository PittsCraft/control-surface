"""`record` and `abandon`: judgments in, derived fields computed by the script (ADR 0012)."""

import json
from pathlib import Path

import pytest
from cli_support import FIXED_NOW, PLAN, Project

from surface_status.build import (
    GATE_EVENT,
    PARAMS,
    current_revision,
    default_slug,
    next_review_pass,
)
from surface_status.events import EVENT_NAMES
from surface_status.journal import read_events
from surface_status.plan_folder import PlanFolder, content_hash


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path)


def _last_line(project: Project) -> dict[str, object]:
    last = project.journal().splitlines()[-1]
    loaded: dict[str, object] = json.loads(last)
    return loaded


def test_every_event_but_the_gate_run_can_be_recorded_by_hand() -> None:
    assert set(PARAMS) == set(EVENT_NAMES) - {GATE_EVENT}


def test_a_recorded_event_is_one_line_stamped_with_the_clock(project: Project) -> None:
    project.plan()
    result = project.record(PLAN, "plan-opened")
    assert result.code == 0
    assert result.json() == {
        "v": 1,
        "ok": True,
        "plan": PLAN,
        "event": "plan-opened",
        "at": "2026-09-29T09:00:00Z",
        "state": "interview",
    }
    assert project.journal() == (
        b'{"v": 1, "at": "2026-09-29T09:00:00Z", "event": "plan-opened", "slug": "feature"}\n'
    )


def test_the_slug_is_the_folder_name_without_its_date_unless_given(project: Project) -> None:
    project.plan()
    project.plan("2026-09-30-other")
    project.record(PLAN, "plan-opened")
    project.record("2026-09-30-other", "plan-opened", "--slug", "custom")
    assert _slug(project, PLAN) == "feature"
    assert _slug(project, "2026-09-30-other") == "custom"
    assert default_slug(PlanFolder(Path("no-date"))) == "no-date"


def _slug(project: Project, name: str) -> object:
    last = (project.plans / name / "journal.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    return json.loads(last)["slug"]


def test_the_hashes_and_the_slices_are_the_ones_of_the_files(project: Project) -> None:
    folder = project.reach("awaiting-approval")
    drafted = [line for line in project.journal().splitlines() if b"plan-drafted" in line]
    fields = json.loads(drafted[0])
    assert fields["overview"] == content_hash((folder / "overview.md").read_bytes())
    assert fields["plan"] == content_hash((folder / "plan.md").read_bytes())
    assert fields["slices"] == [1, 2]
    assert fields["rev"] == 1


def test_the_revision_follows_the_restarts_of_the_draft(project: Project) -> None:
    folder = project.reach("awaiting-approval")
    assert project.record(PLAN, "amendment-received").code == 0
    (folder / "overview.md").write_text("# Overview\nrevised\n", encoding="utf-8")
    (folder / "checks").joinpath("rev-02-01.md").write_text("report\n", encoding="utf-8")
    assert (
        project.record(
            PLAN, "check-done", "--report", "checks/rev-02-01.md", "--omissions", "0"
        ).code
        == 0
    )
    assert project.record(PLAN, "plan-drafted").code == 0
    assert project.record(PLAN, "plan-approved").code == 0
    revisions = [
        json.loads(line)["rev"] for line in project.journal().splitlines() if b'"rev"' in line
    ]
    assert revisions == [1, 1, 2, 2, 2]
    assert current_revision(read_events(folder / "journal.jsonl")) == 2


def test_the_review_pass_counts_the_reviews_already_recorded(project: Project) -> None:
    folder = project.reach("reviewing")
    (folder / "reviews" / "pass-02.md").write_text("report\n", encoding="utf-8")
    review = ["--defects", "1", "--deviations", "0", "--breaks", "0"]
    assert project.record(PLAN, "review-done", "--report", "reviews/pass-01.md", *review).code == 0
    assert project.record(PLAN, "fix-done").code == 0
    assert project.record(PLAN, "review-done", "--report", "reviews/pass-02.md", *review).code == 0
    assert _last_line(project)["pass"] == 2
    assert next_review_pass(read_events(folder / "journal.jsonl")) == 3


def test_a_fix_cites_the_last_review_and_zero_when_there_was_none(project: Project) -> None:
    project.reach("reviewing")
    review = [
        "--report",
        "reviews/pass-01.md",
        "--defects",
        "1",
        "--deviations",
        "0",
        "--breaks",
        "0",
    ]
    project.record(PLAN, "review-done", *review)
    assert project.record(PLAN, "fix-done").code == 0
    assert _last_line(project)["pass"] == 1


def test_a_plan_change_decision_cites_the_pending_proposal(project: Project) -> None:
    project.reach("plan-change-proposed")
    assert project.record(PLAN, "plan-change-refused", "--why", "not needed").code == 0
    assert _last_line(project)["proposal"] == "plan-changes/01.md"


def test_a_plan_change_decision_without_a_proposal_is_refused(project: Project) -> None:
    project.reach("executing")
    before = project.journal()
    result = project.record(PLAN, "plan-change-accepted")
    assert result.code == 1
    assert result.json()["refused"]["code"] == "transition"
    assert project.journal() == before


def test_a_refusal_exits_1_names_the_reason_and_leaves_the_journal_alone(project: Project) -> None:
    project.reach("executing")
    before = project.journal()
    result = project.record(PLAN, "slice-done", "--slice", "9", "--gates", "lint")
    assert result.code == 1
    assert result.json()["ok"] is False
    assert result.json()["refused"] == {
        "code": "slice",
        "reason": "slice 9 is not in the declared list",
    }
    assert project.journal() == before
    text = project.run(
        "record", PLAN, "slice-done", "--slice", "9", "--gates", "lint", as_json=False
    )
    assert text.code == 1
    assert text.err == "refused slice-done (slice): slice 9 is not in the declared list\n"
    assert text.out == ""


def test_an_overview_edited_after_approval_refuses_the_next_slice(project: Project) -> None:
    folder = project.reach("executing")
    (folder / "overview.md").write_text("# Overview\nedited\n", encoding="utf-8")
    result = project.record(PLAN, "slice-done", "--slice", "1", "--gates", "lint")
    assert result.code == 1
    assert result.json()["refused"]["code"] == "overview-changed"


def test_a_missing_overview_is_refused_as_a_missing_file(project: Project) -> None:
    folder = project.reach("awaiting-approval")
    (folder / "overview.md").unlink()
    result = project.record(PLAN, "plan-approved")
    assert result.code == 1
    assert result.json()["refused"] == {
        "code": "file-missing",
        "reason": "cited file missing: overview.md",
    }


def test_a_cited_report_that_does_not_exist_is_refused(project: Project) -> None:
    project.reach("drafting")
    result = project.record(PLAN, "check-done", "--report", "checks/none.md", "--omissions", "0")
    assert result.code == 1
    assert result.json()["refused"]["code"] == "file-missing"


def test_a_report_outside_the_plan_folder_is_refused(project: Project) -> None:
    project.reach("drafting")
    (project.root / "outside.md").write_text("x\n", encoding="utf-8")
    result = project.record(
        PLAN, "check-done", "--report", "../../../outside.md", "--omissions", "0"
    )
    assert result.code == 1
    assert result.json()["refused"]["code"] == "file-missing"


def test_a_derived_field_cannot_be_passed(project: Project) -> None:
    project.plan()
    for extra in (["--rev", "1"], ["--overview", "sha256:" + "0" * 64], ["--at", "2020-01-01"]):
        result = project.record(PLAN, "plan-approved", *extra)
        assert result.code == 2
        assert "unrecognized arguments" in result.out
    assert project.journal() == b""


def test_a_missing_or_malformed_field_is_a_usage_error(project: Project) -> None:
    project.reach("executing")
    before = project.journal()
    for args in (
        ["slice-done", "--slice", "1"],
        ["slice-done", "--slice", "0", "--gates", "lint"],
        ["slice-done", "--slice", "one", "--gates", "lint"],
        ["slice-done", "--slice", "-1", "--gates", "lint"],
        ["slice-done", "--slice", "1", "--gates", "  "],
        ["slice-done", "--slice", "1", "--gates", "two\nlines"],
        ["blocked"],
    ):
        result = project.record(PLAN, *args)
        assert result.code == 2, args
        assert result.json()["ok"] is False
    assert project.journal() == before


def test_an_unknown_event_is_a_usage_error(project: Project) -> None:
    project.plan()
    assert project.record(PLAN, "nonsense").code == 2


def test_the_gate_result_is_never_recorded_by_hand(project: Project) -> None:
    project.reach("reviewing")
    before = project.journal()
    result = project.record(PLAN, "gates-run", "--result", "pass")
    assert result.code == 2
    assert "an exit code is a fact" in result.json()["error"]
    assert project.journal() == before


def test_an_unknown_plan_is_a_usage_error(project: Project) -> None:
    result = project.record("no-such-plan", "plan-opened")
    assert result.code == 2
    assert "no plan folder" in result.json()["error"]


def test_a_plan_is_found_by_name_or_by_path(project: Project) -> None:
    project.reach("interview")
    for reference in (PLAN, f"docs/plans/{PLAN}", str(project.plans / PLAN)):
        assert project.run("show", reference).code == 0, reference


def test_abandon_records_the_abandonment_with_its_reason(project: Project) -> None:
    project.reach("executing")
    result = project.run("abandon", PLAN, "--why", "changed course")
    assert result.code == 0
    assert result.json()["state"] == "abandoned"
    assert _last_line(project) == {
        "v": 1,
        "at": "2026-09-29T09:00:00Z",
        "event": "abandoned",
        "why": "changed course",
    }


def test_abandon_needs_a_reason(project: Project) -> None:
    project.reach("executing")
    before = project.journal()
    assert project.run("abandon", PLAN).code == 2
    assert project.run("abandon", PLAN, "--why", "").code == 2
    assert project.journal() == before


def test_a_plan_over_cannot_be_abandoned_again(project: Project) -> None:
    project.reach("conform")
    before = project.journal()
    result = project.run("abandon", PLAN, "--why", "too late")
    assert result.code == 1
    assert result.json()["refused"]["code"] == "transition"
    assert project.journal() == before


def test_without_a_plan_abandon_takes_the_only_plan_in_progress(project: Project) -> None:
    project.reach("conform", "2026-09-01-done")
    project.reach("executing")
    assert project.run("abandon", "--why", "stop").code == 0
    assert project.run("show", PLAN).json()["state"] == "abandoned"


def test_without_a_plan_several_in_progress_make_the_caller_name_one(project: Project) -> None:
    project.reach("executing", "2026-09-01-one")
    project.reach("executing", "2026-09-02-two")
    result = project.run("abandon", "--why", "stop")
    assert result.code == 2
    assert "2026-09-01-one" in result.json()["error"]
    assert "2026-09-02-two" in result.json()["error"]


def test_without_a_plan_none_in_progress_is_a_usage_error(project: Project) -> None:
    project.reach("conform")
    assert project.run("show").code == 2


def test_the_clock_is_read_once_per_command(project: Project) -> None:
    project.plan()
    assert project.record(PLAN, "plan-opened").json()["at"] == FIXED_NOW.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
