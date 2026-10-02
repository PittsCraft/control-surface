"""`check`: the conformity check for the CI and before merging, abandoned plans included."""

from pathlib import Path

import pytest
from cli_support import PLAN, Project

REQUIRE = ("check", "--require", "conformant")


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path)


def _problem_codes(project: Project, name: str = PLAN) -> list[str]:
    plans = {plan["name"]: plan for plan in project.run(*REQUIRE).json()["plans"]}
    return [problem["code"] for problem in plans[name]["problems"]]


@pytest.mark.parametrize("state", ["interview", "drafting", "awaiting-approval", "executing"])
def test_check_fails_while_a_plan_is_in_progress(project: Project, state: str) -> None:
    project.reach(state)
    result = project.run(*REQUIRE)
    assert result.code == 1
    assert result.json()["ok"] is False
    assert _problem_codes(project) == ["in-progress"]
    assert PLAN in project.run(*REQUIRE, as_json=False).err


def test_check_passes_with_a_plan_abandoned_before_approval(project: Project) -> None:
    project.reach("awaiting-approval")
    assert project.run("abandon", PLAN, "--why", "not wanted").code == 0
    result = project.run(*REQUIRE)
    assert result.code == 0
    assert result.json()["ok"] is True


def test_check_fails_with_a_plan_abandoned_after_approval(project: Project) -> None:
    project.reach("executing")
    assert project.run("abandon", PLAN, "--why", "changed course").code == 0
    result = project.run(*REQUIRE, as_json=False)
    assert result.code == 1
    assert PLAN in result.err
    assert "abandoned after its approval" in result.err


def test_the_alarm_after_an_abandon_says_it_stays_even_if_the_code_was_removed(
    project: Project,
) -> None:
    project.reach("reviewing")
    project.run("abandon", PLAN, "--why", "too late")
    messages = [
        problem["message"]
        for plan in project.run(*REQUIRE).json()["plans"]
        for problem in plan["problems"]
    ]
    assert len(messages) == 1
    assert "stays even if that code was removed" in messages[0]
    assert "merge knowingly" in messages[0]


def test_check_passes_with_a_conformant_plan(project: Project) -> None:
    project.reach("conformant")
    assert project.run(*REQUIRE).code == 0


def test_a_conformant_plan_whose_blueprint_is_edited_fails_the_check_naming_the_plan(
    project: Project,
) -> None:
    folder = project.reach("conformant")
    (folder / "blueprint.md").write_text("# Blueprint\nedited after conformity\n", encoding="utf-8")
    result = project.run(*REQUIRE, as_json=False)
    assert result.code == 1
    assert PLAN in result.err
    assert "blueprint-changed" in result.err
    assert _problem_codes(project) == ["blueprint-changed"]


def test_the_same_plan_restored_to_its_approved_content_passes_again(project: Project) -> None:
    folder = project.reach("conformant")
    approved = (folder / "blueprint.md").read_bytes()
    (folder / "blueprint.md").write_text("# Blueprint\nedited\n", encoding="utf-8")
    assert project.run(*REQUIRE).code == 1
    (folder / "blueprint.md").write_bytes(approved)
    assert project.run(*REQUIRE).code == 0


def test_a_conformant_plan_whose_blueprint_was_deleted_fails(project: Project) -> None:
    folder = project.reach("conformant")
    (folder / "blueprint.md").unlink()
    assert project.run(*REQUIRE).code == 1
    assert _problem_codes(project) == ["blueprint-missing"]


def test_the_hash_of_a_checkout_with_crlf_endings_still_passes(project: Project) -> None:
    folder = project.reach("conformant")
    (folder / "blueprint.md").write_bytes(b"# Blueprint\r\n")
    assert project.run(*REQUIRE).code == 0


def test_check_names_every_plan_and_fails_if_one_does(project: Project) -> None:
    project.reach("conformant", "2026-09-01-done")
    project.reach("executing", "2026-09-02-running")
    payload = project.run(*REQUIRE).json()
    assert [(plan["name"], plan["ok"]) for plan in payload["plans"]] == [
        ("2026-09-01-done", True),
        ("2026-09-02-running", False),
    ]
    assert payload["ok"] is False


def test_check_of_named_plans_leaves_the_others_out(project: Project) -> None:
    project.reach("conformant", "2026-09-01-done")
    project.reach("executing", "2026-09-02-running")
    assert project.run(*REQUIRE, "2026-09-01-done").code == 0
    assert project.run(*REQUIRE, "2026-09-02-running").code == 1


def test_check_without_require_only_validates_the_journals(project: Project) -> None:
    project.reach("executing")
    result = project.run("check")
    assert result.code == 0
    assert result.json()["require"] is None


def test_check_with_no_plan_passes(project: Project) -> None:
    assert project.run(*REQUIRE).code == 0
    assert project.run("check").code == 0


def test_a_folder_without_a_journal_is_not_a_plan_yet(project: Project) -> None:
    project.plan("2026-09-03-not-opened")
    assert project.run(*REQUIRE).json()["plans"] == []


@pytest.mark.parametrize("require", [[], ["--require", "conformant"]])
def test_an_unreadable_journal_is_exit_2_with_the_line_at_fault(
    project: Project, require: list[str]
) -> None:
    folder = project.reach("executing")
    journal = folder / "journal.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"v": 1', '"v": 2')
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = project.run("check", *require)
    assert result.code == 2
    assert _codes(result.json()) == ["journal-unreadable"]
    assert "line 2" in result.out


def test_a_journal_the_machine_refuses_to_replay_is_exit_2(project: Project) -> None:
    folder = project.reach("interview")
    with (folder / "journal.jsonl").open("a", encoding="utf-8") as journal:
        journal.write('{"v": 1, "at": "2026-09-29T09:00:00Z", "event": "conformant", ')
        journal.write('"conformity": "conformity.md", "blueprint": "sha256:' + "0" * 64 + '"}\n')
    assert project.run("check").code == 2


def _codes(payload: dict[str, object]) -> list[str]:
    plans: list[dict[str, list[dict[str, str]]]] = payload["plans"]  # type: ignore[assignment]
    return [problem["code"] for plan in plans for problem in plan["problems"]]
