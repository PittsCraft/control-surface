"""The documented JSON shape of `resolve`, `commits` and `pr-body`.

The contract is in ARCHITECTURE.md, Command line contract.
"""

from pathlib import Path

import pytest
from cli_support import assert_golden
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
    assert list(payload["plans"][0]) == ["name", "state", "hand", "overview", "plan", "decisions"]


def test_golden_pr_body_with_decisions(repo: Repo) -> None:
    repo.branch("feature")
    folder = repo.plan("executing", A)
    note = "reviews/suspicion-01.md"
    (folder / note).write_text("dismissed\n", encoding="utf-8")
    steps = (
        ("plan-amended", "--slice", "1", "--why", "the parser needs a second pass"),
        ("slice-done", "--slice", "1", "--gates", "lint"),
        ("break-suspected", "--slice", "2", "--why", "the export needs a column"),
        ("suspicion-dismissed", "--slice", "2", "--report", note),
    )
    for step in steps:
        assert repo.run("record", A, *step).code == 0, step
    result = repo.run("pr-body")
    assert [list(item) for item in result.json()["plans"][0]["decisions"]] == [
        ["event", "slice", "why", "note"],
        ["event", "slice", "why", "note"],
    ]
    assert_golden("pr-body.json", result.out)
