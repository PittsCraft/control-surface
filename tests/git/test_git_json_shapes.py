"""The documented JSON shape of `resolve`, `commits` and `pr-body`.

The contract is in ARCHITECTURE.md, Command line contract.
"""

from pathlib import Path

import pytest
from git_support import Repo, isolate_git

A = "2026-09-01-alpha"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    isolate_git(monkeypatch)
    return Repo(tmp_path)


def test_the_resolve_answer_has_its_documented_fields(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("executing", A)
    payload = repo.resolve("execute").json()
    assert list(payload) == [
        "v",
        "ok",
        "for",
        "outcome",
        "branch",
        "plan",
        "candidates",
        "other_plans",
        "elsewhere",
    ]
    assert payload["v"] == 1
    assert payload["candidates"] == [{"name": A, "state": "executing"}]


def test_the_commits_answer_has_its_documented_fields(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("executing", A)
    repo.commit("plan A")
    payload = repo.run("commits", A).json()
    assert list(payload) == ["v", "plan", "main", "base", "commits", "unowned"]
    assert list(payload["commits"][0]) == ["hash", "subject"]


def test_the_pr_body_answer_has_its_documented_fields(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("executing", A)
    payload = repo.run("pr-body").json()
    assert list(payload) == ["v", "branch", "plans", "body"]
    assert list(payload["plans"][0]) == ["name", "state", "hand", "overview", "plan"]
