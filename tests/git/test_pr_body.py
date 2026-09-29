"""`pr-body`: the description lists every plan of the branch, with its state and its links."""

from pathlib import Path

import pytest
from git_support import Repo, isolate_git

A = "2026-09-01-alpha"
B = "2026-09-02-beta"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    isolate_git(monkeypatch)
    return Repo(tmp_path)


def test_the_description_lists_every_plan_of_the_branch_with_state_and_links(
    repo: Repo,
) -> None:
    repo.plan("conform", "2026-08-01-old")
    repo.commit("kept on main")
    repo.branch("feature/x")
    repo.plan("executing", A)
    repo.plan("conform", B)
    payload = repo.run("pr-body").json()
    assert payload["v"] == 1
    assert payload["branch"] == "feature/x"
    assert [(row["name"], row["state"]) for row in payload["plans"]] == [
        (A, "executing"),
        (B, "conform"),
    ]
    body = payload["body"]
    assert body.startswith("## Plans on this branch")
    assert "old" not in body
    for name, state in ((A, "executing"), (B, "conform")):
        assert f"| `{name}` | {state} |" in body
        assert f"[overview.md](docs/plans/{name}/overview.md)" in body
        assert f"[plan.md](docs/plans/{name}/plan.md)" in body


def test_the_text_is_the_body_alone(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("executing", A)
    text = repo.run("pr-body", as_json=False).out
    assert text == repo.run("pr-body").json()["body"]


def test_links_are_absolute_when_origin_is_on_github(repo: Repo) -> None:
    repo.git("remote", "add", "origin", "git@github.com:owner/host.git")
    repo.branch("feature/my#plan")
    repo.plan("executing", A)
    (row,) = repo.run("pr-body").json()["plans"]
    base = "https://github.com/owner/host/blob/feature/my%23plan"
    assert row["overview"] == f"[overview.md]({base}/docs/plans/{A}/overview.md)"
    assert row["plan"] == f"[plan.md]({base}/docs/plans/{A}/plan.md)"


@pytest.mark.parametrize(
    "remote",
    [
        "https://github.com/owner/host.git",
        "https://user@github.com/owner/host",
        "ssh://git@github.com/owner/host.git",
    ],
)
def test_every_github_form_of_the_remote_gives_the_same_links(repo: Repo, remote: str) -> None:
    repo.git("remote", "add", "origin", remote)
    repo.branch("feature")
    repo.plan("executing", A)
    (row,) = repo.run("pr-body").json()["plans"]
    assert row["plan"].startswith("[plan.md](https://github.com/owner/host/blob/feature/")


def test_a_file_the_plan_does_not_have_is_said_missing(repo: Repo) -> None:
    repo.branch("feature")
    folder = repo.plan("executing", A)
    (folder / "overview.md").rename(folder / "overview.old")
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["overview"] is None
    assert payload["plans"][0]["plan"] is not None
    assert "| missing |" in payload["body"]


def test_a_branch_without_a_plan_has_no_description(repo: Repo) -> None:
    repo.branch("feature")
    result = repo.run("pr-body")
    assert result.code == 1
    assert result.json()["ok"] is False
    assert "no plan on this branch" in repo.run("pr-body", as_json=False).err


def test_an_unreadable_journal_stops_the_description(repo: Repo) -> None:
    repo.branch("feature")
    folder = repo.plan("executing", A)
    (folder / "journal.jsonl").write_text("not json\n", encoding="utf-8")
    assert repo.run("pr-body").code == 2


def test_a_description_needs_a_git_work_tree(tmp_path: Path) -> None:
    from cli_support import Project  # noqa: PLC0415 (a project that is not a repository)

    project = Project(tmp_path)
    project.reach("executing", A)
    assert project.run("pr-body").code == 2
