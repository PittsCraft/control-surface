"""`pr-body`: the description lists every plan of the branch, with its state and its links.

Then, for information, the decisions agents took within the contract, one line each.
"""

from pathlib import Path

import pytest
from git_support import Repo, isolate_git

from surface_status.events import (
    BreakSuspected,
    PlanAmended,
    PlanChangeProposed,
    SliceDone,
    SuspicionDismissed,
)
from surface_status.pr_body import DECISIONS_TITLE, Decision, decisions

A = "2026-09-01-alpha"
B = "2026-09-02-beta"
NOTE = "reviews/suspicion-01.md"


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


# The decisions agents took within the contract.


def _decide(repo: Repo, name: str) -> Path:
    """Drive a plan through an amendment of slice 1, then a dismissed suspicion during slice 2."""
    folder = repo.plan("executing", name)
    steps = (
        ("plan-amended", "--slice", "1", "--why", "the parser needs a second pass"),
        ("slice-done", "--slice", "1", "--gates", "lint"),
        ("break-suspected", "--slice", "2", "--why", "the export needs a column"),
    )
    for step in steps:
        assert repo.run("record", name, *step).code == 0, step
    (folder / NOTE).write_text("dismissed\n", encoding="utf-8")
    dismissed = ("suspicion-dismissed", "--slice", "2", "--report", NOTE)
    assert repo.run("record", name, *dismissed).code == 0
    return folder


def test_amendments_and_dismissed_suspicions_are_listed_one_line_each(repo: Repo) -> None:
    repo.branch("feature")
    _decide(repo, A)
    payload = repo.run("pr-body").json()
    note = f"[{NOTE}](docs/plans/{A}/{NOTE})"
    assert payload["plans"][0]["decisions"] == [
        {
            "event": "plan-amended",
            "slice": 1,
            "why": "the parser needs a second pass",
            "note": None,
        },
        {
            "event": "suspicion-dismissed",
            "slice": 2,
            "why": "the export needs a column",
            "note": note,
        },
    ]
    body = payload["body"]
    assert body.index("| Plan | State |") < body.index(DECISIONS_TITLE)
    section = body[body.index(DECISIONS_TITLE) :]
    assert "For information" in section
    assert f"- `{A}`, slice 1: plan amended: the parser needs a second pass\n" in section
    dismissed = (
        f"- `{A}`, slice 2: suspected break dismissed by a reviewer: the export needs a column"
    )
    assert f"{dismissed} (note: {note})\n" in section
    assert section.rstrip().endswith("edit the plans, not this text.")


def test_the_decisions_of_every_plan_are_listed_under_its_name(repo: Repo) -> None:
    repo.branch("feature")
    _decide(repo, A)
    repo.plan("executing", B)
    assert repo.run("record", B, "plan-amended", "--slice", "2", "--why", "renamed").code == 0
    body = repo.run("pr-body").json()["body"]
    lines = [line for line in body.splitlines() if line.startswith("- `")]
    assert [line.split(":")[0] for line in lines] == [
        f"- `{A}`, slice 1",
        f"- `{A}`, slice 2",
        f"- `{B}`, slice 2",
    ]


def test_nothing_is_listed_when_no_agent_decided_anything(repo: Repo) -> None:
    repo.branch("feature")
    repo.plan("conform", A)
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["decisions"] == []
    assert DECISIONS_TITLE not in payload["body"]
    assert "For information" not in payload["body"]


def test_a_note_no_longer_on_disk_is_said_missing(repo: Repo) -> None:
    repo.branch("feature")
    folder = _decide(repo, A)
    (folder / NOTE).unlink()
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["decisions"][1]["note"] is None
    assert "(note: missing)" in payload["body"]


def test_a_dismissal_without_a_recorded_suspicion_has_no_reason(repo: Repo) -> None:
    repo.branch("feature")
    folder = repo.plan("executing", A)
    (folder / NOTE).write_text("dismissed\n", encoding="utf-8")
    dismissed = ("suspicion-dismissed", "--slice", "1", "--report", NOTE)
    assert repo.run("record", A, *dismissed).code == 0
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["decisions"][0]["why"] is None
    assert f"- `{A}`, slice 1: suspected break dismissed by a reviewer (note: " in payload["body"]


def test_decisions_follow_the_journal_and_keep_a_reason_on_one_line() -> None:
    events = (
        PlanAmended(slice_=1, why="first\nsecond  line", plan="sha256:0", slices=(1, 2, 3)),
        BreakSuspected(slice_=2, why="a column\r\nmore"),
        PlanChangeProposed(proposal="plan-changes/01.md", slice_=2),
        BreakSuspected(slice_=3, why="an endpoint"),
        SuspicionDismissed(slice_=3, report=NOTE),
        SliceDone(slice_=3, gates="lint"),
        SuspicionDismissed(slice_=2, report="reviews/suspicion-02.md"),
    )
    assert decisions(events) == [
        Decision("plan-amended", 1, "first second line", None),
        Decision("suspicion-dismissed", 3, "an endpoint", NOTE),
        Decision("suspicion-dismissed", 2, None, "reviews/suspicion-02.md"),
    ]
