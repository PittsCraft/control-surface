"""`commits`: which commits belong to which plan, and the diff a merge of main leaves alone."""

from pathlib import Path

import pytest
from git_support import Repo, isolate_git

A = "2026-09-01-alpha"
B = "2026-09-02-beta"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    isolate_git(monkeypatch)
    return Repo(tmp_path)


def _subjects(rows: list[dict[str, str]]) -> list[str]:
    return [row["subject"] for row in rows]


def _open(repo: Repo, name: str) -> None:
    repo.project.plans.mkdir(parents=True, exist_ok=True)
    repo.project.plan(name)
    assert repo.run("record", name, "plan-opened").code == 0


def test_commits_split_by_the_plan_whose_journal_they_extend(repo: Repo) -> None:
    repo.branch("feature")
    _open(repo, A)
    repo.commit("open A")
    _open(repo, B)
    repo.commit("open B")
    assert repo.run("record", A, "interview-closed").code == 0
    repo.write("src/app.py")
    repo.commit("A closes its interview, with code")
    repo.write("src/by_hand.py")
    repo.commit("the developer's own commit")
    for plan, expected in ((A, ["open A", "A closes its interview, with code"]), (B, ["open B"])):
        payload = repo.run("commits", plan).json()
        assert payload["plan"] == plan
        assert _subjects(payload["commits"]) == expected
        assert _subjects(payload["unowned"]) == ["the developer's own commit"]


def test_a_commit_that_extends_two_journals_belongs_to_both(repo: Repo) -> None:
    repo.branch("feature")
    _open(repo, A)
    _open(repo, B)
    repo.commit("open both")
    for plan in (A, B):
        payload = repo.run("commits", plan).json()
        assert _subjects(payload["commits"]) == ["open both"]
        assert payload["unowned"] == []


def test_a_commit_that_touches_a_plan_without_its_journal_belongs_to_no_plan(
    repo: Repo,
) -> None:
    repo.branch("feature")
    _open(repo, A)
    repo.commit("open A")
    repo.write(f"docs/plans/{A}/exploration.md")
    repo.commit("notes in the plan folder")
    payload = repo.run("commits", A).json()
    assert _subjects(payload["commits"]) == ["open A"]
    assert _subjects(payload["unowned"]) == ["notes in the plan folder"]


def test_commits_come_oldest_first_with_their_hash(repo: Repo) -> None:
    repo.branch("feature")
    _open(repo, A)
    first = repo.commit("first")
    assert repo.run("record", A, "interview-closed").code == 0
    second = repo.commit("second")
    payload = repo.run("commits", A).json()
    assert [row["hash"] for row in payload["commits"]] == [first, second]
    assert payload["base"] == repo.git("rev-parse", "main")
    assert payload["main"] == "main"


def test_the_text_of_commits_shows_both_lists(repo: Repo) -> None:
    repo.branch("feature")
    _open(repo, A)
    repo.commit("open A")
    repo.write("src/app.py")
    repo.commit("by hand")
    text = repo.run("commits", A, as_json=False).out
    assert f"plan: {A}" in text
    assert "commits of the plan:" in text
    assert "open A" in text
    assert "commits that belong to no plan:" in text
    assert "by hand" in text


def test_a_branch_without_commits_has_empty_lists(repo: Repo) -> None:
    repo.branch("feature")
    _open(repo, A)
    payload = repo.run("commits", A).json()
    assert payload["commits"] == []
    assert payload["unowned"] == []


def test_a_merge_of_main_into_the_branch_adds_nothing_to_the_reviewed_diff(repo: Repo) -> None:
    repo.branch("feature")
    _open(repo, A)
    repo.write("src/feature.py")
    repo.commit("the feature")
    repo.switch("main")
    repo.write("src/other.py")
    repo.write(f"docs/plans/{B}/journal.jsonl", "")
    repo.commit("someone else's work lands on main")
    repo.switch("feature")
    before = repo.run("commits", A).json()["base"]
    assert "src/other.py" in repo.git(
        "diff", "--no-renames", "--name-only", "main", "HEAD"
    )  # the naive diff
    assert "src/other.py" not in repo.git("diff", "--no-renames", "--name-only", before, "HEAD")
    repo.git("merge", "-q", "--no-ff", "-m", "merge main into feature", "main")
    payload = repo.run("commits", A).json()
    assert payload["base"] == repo.git("rev-parse", "main")
    reviewed = repo.git("diff", "--no-renames", "--name-only", payload["base"], "HEAD").splitlines()
    assert sorted(reviewed) == [
        f"docs/plans/{A}/blueprint.md",
        f"docs/plans/{A}/journal.jsonl",
        f"docs/plans/{A}/plan.md",
        "src/feature.py",
    ]
    assert "src/other.py" not in reviewed
    every = _subjects(payload["commits"]) + _subjects(payload["unowned"])
    assert every == ["the feature"]
    assert "someone else's work lands on main" not in every
    assert "merge main into feature" not in every
    assert repo.names() == [A]


def test_commits_outside_a_git_work_tree_is_a_usage_error(tmp_path: Path) -> None:
    from cli_support import Project  # noqa: PLC0415 (a project that is not a repository)

    project = Project(tmp_path)
    project.reach("executing", A)
    result = project.run("commits", A)
    assert result.code == 2
    assert "not in a git work tree" in result.json()["error"]
