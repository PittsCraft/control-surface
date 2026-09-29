"""`resolve` and the plans of a branch: several plans per branch, plans kept on main (ADR 0015)."""

from pathlib import Path

import pytest
from git_support import Repo, isolate_git

A = "2026-09-01-alpha"
B = "2026-09-02-beta"
C = "2026-09-03-gamma"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    isolate_git(monkeypatch)
    return Repo(tmp_path)


def test_with_two_plans_on_a_branch_resolve_names_the_right_one_per_command(
    repo: Repo,
) -> None:
    repo.branch("feature")
    repo.plan("executing", A)
    repo.plan("drafting", B)
    for_execute = repo.resolve("execute")
    for_plan = repo.resolve("plan")
    assert (for_execute.code, for_execute.json()["plan"]) == (0, A)
    assert (for_plan.code, for_plan.json()["plan"]) == (0, B)
    assert for_execute.json()["outcome"] == "one"
    assert for_execute.json()["other_plans"] == [{"name": B, "state": "drafting"}]
    assert repo.run("resolve", "--for", "execute", as_json=False).out == f"{A}\n"


def test_resolve_lists_both_plans_when_both_match(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("awaiting-approval", A)
    repo.plan("awaiting-approval", B)
    result = repo.resolve("execute")
    assert result.code == 1
    payload = result.json()
    assert payload["ok"] is False
    assert payload["outcome"] == "several"
    assert payload["plan"] is None
    assert [item["name"] for item in payload["candidates"]] == [A, B]
    text = repo.run("resolve", "--for", "execute", as_json=False)
    assert text.code == 1
    assert A in text.err
    assert B in text.err
    assert "ask the developer" in text.err
    assert text.out == ""


def test_resolve_says_when_no_plan_matches_and_shows_the_others(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("interview", A)
    result = repo.resolve("execute")
    assert result.code == 1
    payload = result.json()
    assert payload["outcome"] == "none"
    assert payload["candidates"] == []
    assert payload["other_plans"] == [{"name": A, "state": "interview"}]
    text = repo.run("resolve", "--for", "execute", as_json=False).err
    assert "no plan of feature for surface-execute" in text
    assert f"{A} (interview)" in text


@pytest.mark.parametrize(
    ("state", "plan_sees", "execute_sees"),
    [
        ("interview", True, False),
        ("drafting", True, False),
        ("awaiting-approval", True, True),
        ("executing", False, True),
        ("reviewing", False, True),
        ("conform", False, False),
    ],
)
def test_each_command_sees_the_states_it_accepts(
    repo: Repo, state: str, *, plan_sees: bool, execute_sees: bool
) -> None:
    repo.branch("feature")
    repo.plan(state, A)
    assert (repo.resolve("plan").code == 0) is plan_sees
    assert (repo.resolve("execute").code == 0) is execute_sees


def test_a_blocked_plan_is_seen_by_execute_only_when_it_stopped_during_the_execution(
    repo: Repo,
) -> None:
    repo.branch("feature")
    repo.plan("drafting", A)
    repo.plan("executing", B)
    assert repo.run("record", A, "blocked", "--why", "stuck").code == 0
    assert repo.run("record", B, "blocked", "--why", "stuck").code == 0
    assert [item["name"] for item in repo.resolve("plan").json()["candidates"]] == [A, B]
    assert repo.resolve("execute").json()["plan"] == B


def test_an_explicit_argument_wins_whatever_the_state_and_the_branch(repo: Repo) -> None:
    repo.plan("conform", A)
    repo.commit("a plan kept on main")
    repo.branch("feature")
    repo.plan("executing", B)
    for command in ("plan", "execute"):
        for plan in (A, B):
            result = repo.resolve(command, plan)
            assert result.code == 0
            assert result.json()["plan"] == plan
            assert result.json()["outcome"] == "explicit"
    assert repo.resolve("execute", "2026-01-01-unknown").code == 2


def test_terminal_plan_folders_kept_on_main_are_neither_resolved_nor_listed(repo: Repo) -> None:
    repo.plan("conform", A)
    repo.plan("executing", B)  # not terminal, but already on main: not this branch's plan
    repo.commit("plans kept on main after earlier merges")
    repo.branch("feature")
    assert repo.names() == []
    for command in ("plan", "execute"):
        result = repo.resolve(command)
        assert result.code == 1
        assert result.json()["outcome"] == "none"
        assert result.json()["other_plans"] == []
    assert repo.run("check", "--require", "conform").code == 0
    assert repo.run("show").code == 2
    assert repo.run("abandon", "--why", "nothing to abandon").code == 2


def test_the_plans_of_a_branch_are_those_it_adds_and_only_those(repo: Repo) -> None:
    repo.plan("conform", A)
    repo.commit("kept on main")
    repo.branch("feature")
    repo.plan("executing", B)
    assert repo.names() == [B]
    assert repo.resolve("execute").json()["plan"] == B
    repo.commit("plan B")
    assert repo.names() == [B]


def test_a_plan_opened_and_not_yet_committed_is_the_plan_of_the_branch(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("interview", A)
    assert repo.git("status", "--porcelain").startswith("??")
    assert repo.resolve("plan").json()["plan"] == A


def test_show_and_abandon_without_a_plan_take_the_one_plan_of_the_branch(repo: Repo) -> None:
    repo.plan("executing", A)  # in progress on main: not this branch's
    repo.commit("kept on main")
    repo.branch("feature")
    repo.plan("executing", B)
    assert repo.run("show").json()["plan"] == B
    abandoned = repo.run("abandon", "--why", "changed course")
    assert abandoned.code == 0
    assert abandoned.json()["plan"] == B
    assert repo.run("show", A).json()["state"] == "executing"


def test_show_and_abandon_without_a_plan_name_the_candidates_when_several(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("executing", A)
    repo.plan("drafting", B)
    for args in (("show",), ("abandon", "--why", "x")):
        result = repo.run(*args)
        assert result.code == 2
        assert A in result.json()["error"]
        assert B in result.json()["error"]
    assert repo.run("show", B).code == 0


def test_the_list_and_the_check_work_on_the_plans_of_the_branch(repo: Repo) -> None:
    repo.plan("executing", A)  # in progress on main
    repo.commit("kept on main")
    repo.branch("feature")
    repo.plan("conform", B)
    assert repo.names() == [B]
    checked = repo.run("check", "--require", "conform")
    assert checked.code == 0
    assert [plan["name"] for plan in checked.json()["plans"]] == [B]
    repo.plan("executing", C)
    failed = repo.run("check", "--require", "conform")
    assert failed.code == 1
    assert [plan["name"] for plan in failed.json()["plans"] if not plan["ok"]] == [C]


def test_from_main_the_unmerged_branches_are_scanned_and_their_plans_listed(repo: Repo) -> None:
    repo.branch("feature-a")
    repo.plan("executing", A)
    repo.commit("plan A")
    repo.switch("main")
    repo.branch("feature-b")
    repo.plan("drafting", B)
    repo.commit("plan B")
    repo.switch("main")
    repo.branch("feature-done")
    repo.plan("conform", C)
    repo.commit("plan C")
    repo.switch("main")
    repo.merge("feature-done")
    assert repo.names() == []
    result = repo.resolve("plan")
    assert result.code == 1
    assert result.json()["branch"] == "main"
    assert result.json()["elsewhere"] == [
        {
            "branch": "feature-b",
            "plan": B,
            "state": "drafting",
            "suggestion": "git switch feature-b",
        }
    ]
    execute = repo.resolve("execute").json()["elsewhere"]
    assert [(item["branch"], item["plan"]) for item in execute] == [("feature-a", A)]
    text = repo.run("resolve", "--for", "execute", as_json=False).err
    assert "in progress on branch feature-a" in text
    assert "switch with `git switch feature-a`" in text


def test_elsewhere_is_scanned_from_main_only(repo: Repo) -> None:
    repo.branch("feature-a")
    repo.plan("executing", A)
    repo.commit("plan A")
    repo.switch("main")
    repo.branch("feature-b")
    assert repo.resolve("execute").json()["elsewhere"] == []


def test_a_plan_of_an_unmerged_branch_with_an_unreadable_journal_is_reported_not_fatal(
    repo: Repo,
) -> None:
    repo.branch("feature-a")
    folder = repo.plan("executing", A)
    (folder / "journal.jsonl").write_text("not json\n", encoding="utf-8")
    repo.commit("broken plan")
    repo.switch("main")
    result = repo.resolve("execute")
    (item,) = result.json()["elsewhere"]
    assert item["plan"] == A
    assert item["state"] is None
    assert "line 1" in item["error"]
    assert "unreadable" in repo.run("resolve", "--for", "execute", as_json=False).err


def test_the_main_branch_is_master_when_there_is_no_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_git(monkeypatch)
    repo = Repo(tmp_path, main="master")
    repo.plan("conform", A)
    repo.commit("kept on master")
    repo.branch("feature")
    repo.plan("executing", B)
    assert repo.names() == [B]


def test_the_main_branch_is_origin_head_even_when_the_local_main_is_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_git(monkeypatch)
    (tmp_path / "origin").mkdir()
    origin = Repo(tmp_path / "origin")
    host = Repo(tmp_path / "clone", origin=origin)
    origin.plan("conform", A)
    origin.commit("merged on origin, not pulled")
    host.git("fetch", "-q", "origin")
    host.git("switch", "-q", "-c", "feature", "origin/main")  # local main stays behind
    host.plan("executing", B)
    assert host.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD") == "origin/main"
    assert host.names() == [B]
    assert host.resolve("execute").json()["plan"] == B


def ci_checkout(tmp_path: Path, main: str, *, detached: bool) -> Repo:
    """Clone as a CI checkout of a pull request leaves it: no local main, no `origin/HEAD`."""
    (tmp_path / "origin").mkdir()
    origin = Repo(tmp_path / "origin", main=main)
    origin.plan("conform", A)
    origin.commit("merged earlier")
    host = Repo(tmp_path / "clone", origin=origin)
    host.git("switch", "-q", "-c", "feature")
    host.plan("executing", B)
    host.commit("the pull request")
    if detached:
        host.git("switch", "-q", "--detach")
    host.git("branch", "-q", "-D", main)
    host.git("symbolic-ref", "-d", "refs/remotes/origin/HEAD")
    assert host.git("branch", "--list", main) == ""
    return host


@pytest.mark.parametrize("main", ["main", "master"])
@pytest.mark.parametrize("detached", [False, True])
def test_the_main_branch_is_found_on_origin_in_a_checkout_without_a_local_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, main: str, *, detached: bool
) -> None:
    isolate_git(monkeypatch)
    host = ci_checkout(tmp_path, main, detached=detached)
    resolved = host.resolve("execute")
    assert (resolved.code, resolved.json()["plan"]) == (0, B)
    assert host.run("commits", B).json()["main"] == f"origin/{main}"
    assert host.names() == [B]  # the plan merged earlier is not the branch's


def test_check_does_not_fail_on_usage_in_a_checkout_without_a_local_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_git(monkeypatch)
    host = ci_checkout(tmp_path, "main", detached=True)
    assert host.run("check").code == 0
    required = host.run("check", "--require", "conform")
    assert required.code == 1  # the plan is not conform: a verdict, not exit 2


def test_a_repository_without_a_main_branch_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_git(monkeypatch)
    repo = Repo(tmp_path, main="trunk")
    result = repo.run()
    assert result.code == 2
    assert "cannot find the main branch" in result.json()["error"]


def test_without_git_every_plan_that_holds_a_journal_counts(tmp_path: Path) -> None:
    from cli_support import Project  # noqa: PLC0415 (a project that is not a repository)

    project = Project(tmp_path)
    project.reach("executing", A)
    project.reach("conform", B)
    assert project.run("resolve", "--for", "execute").json()["plan"] == A
    assert [row["name"] for row in project.run().json()["plans"]] == [A, B]
