"""`pr-body`: the description lists every plan of the branch, with its state and its links.

Then the changed files of the critical zones, for the developer to read themselves, and, for
information, the decisions agents took within the contract, one line each.
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
from surface_status.pr_body import CRITICAL_TITLE, DECISIONS_TITLE, Decision, decisions

A = "2026-09-01-alpha"
B = "2026-09-02-beta"
NOTE = "reviews/suspicion-01.md"
REVIEW = (
    "review-done",
    "--report",
    "reviews/pass-01.md",
    "--defects",
    "0",
    "--deviations",
    "0",
    "--breaks",
    "0",
)
CONFORMANT = ("conformant", "--conformity", "conformity.md")
FOOTER = "Refreshed by `surface-status pr-body`; edit the plans, not this text."


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    isolate_git(monkeypatch)
    return Repo(tmp_path)


def test_the_description_lists_every_plan_of_the_branch_with_state_and_links(
    repo: Repo,
) -> None:
    repo.plan("conformant", "2026-08-01-old")
    repo.commit("kept on main")
    repo.branch("feature/x")
    repo.plan("executing", A)
    repo.plan("conformant", B)
    payload = repo.run("pr-body").json()
    assert payload["v"] == 1
    assert payload["branch"] == "feature/x"
    assert [(row["name"], row["state"]) for row in payload["plans"]] == [
        (A, "executing"),
        (B, "conformant"),
    ]
    body = payload["body"]
    assert body.startswith("## Plans on this branch")
    assert "old" not in body
    for name, state in ((A, "executing"), (B, "conformant")):
        assert f"| `{name}` | {state} |" in body
        assert f"[blueprint.md](docs/plans/{name}/blueprint.md)" in body
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
    assert row["blueprint"] == f"[blueprint.md]({base}/docs/plans/{A}/blueprint.md)"
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
    (folder / "blueprint.md").rename(folder / "blueprint.old")
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["blueprint"] is None
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
    repo.plan("conformant", A)
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


# The changed files of the critical zones, which the developer reads themselves.


def _block(*paths: str) -> str:
    return "1. Proved.\n\n```critical-files\n" + "".join(f"{path}\n" for path in paths) + "```\n"


def _conformant(repo: Repo, name: str, conformity: str) -> Path:
    """Finish a plan in `reviewing`: a clean review, its proof, a commit, then `conformant`."""
    folder = repo.project.plans / name
    assert repo.run("record", name, *REVIEW).code == 0
    (folder / "conformity.md").write_text(conformity, encoding="utf-8")
    repo.commit(f"the work and the review of {name}")
    assert repo.run("record", name, *CONFORMANT).code == 0
    return folder


def test_the_changed_files_of_the_critical_zones_are_listed_for_the_developer_to_read(
    repo: Repo,
) -> None:
    repo.branch("feature")
    repo.write("billing/pay.py")
    repo.write("billing/tax rules.py")
    repo.plan("reviewing", A)
    _conformant(repo, A, _block("billing/pay.py", "billing/tax rules.py"))
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["critical_files"] == [
        {"path": "billing/pay.py", "link": "[billing/pay.py](billing/pay.py)"},
        {"path": "billing/tax rules.py", "link": "[billing/tax rules.py](billing/tax%20rules.py)"},
    ]
    body = payload["body"]
    assert "for you to read yourself" in CRITICAL_TITLE
    assert body.index("| Plan | State |") < body.index(CRITICAL_TITLE)
    section = body[body.index(CRITICAL_TITLE) :]
    assert "A conformant plan leaves nothing else to check" in section
    assert f"- `{A}`: [billing/pay.py](billing/pay.py)\n" in section
    assert f"- `{A}`: [billing/tax rules.py](billing/tax%20rules.py)\n" in section
    assert section.rstrip().endswith(FOOTER)


def test_the_files_to_read_are_linked_like_the_other_files_of_the_description(repo: Repo) -> None:
    repo.git("remote", "add", "origin", "git@github.com:owner/host.git")
    repo.branch("feature/my#plan")
    repo.write("billing/pay.py")
    repo.plan("reviewing", A)
    _conformant(repo, A, _block("billing/pay.py"))
    (row,) = repo.run("pr-body").json()["plans"]
    base = "https://github.com/owner/host/blob/feature/my%23plan"
    assert row["critical_files"] == [
        {"path": "billing/pay.py", "link": f"[billing/pay.py]({base}/billing/pay.py)"}
    ]
    assert row["blueprint"] == f"[blueprint.md]({base}/docs/plans/{A}/blueprint.md)"


def test_the_files_to_read_come_before_the_decisions_given_for_information(repo: Repo) -> None:
    repo.branch("feature")
    repo.write("billing/pay.py")
    _decide(repo, A)
    assert repo.run("record", A, "slice-done", "--slice", "2", "--gates", "lint").code == 0
    _conformant(repo, A, _block("billing/pay.py"))
    body = repo.run("pr-body").json()["body"]
    table, critical, decided = (
        body.index("| Plan | State |"),
        body.index(CRITICAL_TITLE),
        body.index(DECISIONS_TITLE),
    )
    assert table < critical < decided
    assert body.rstrip().endswith(FOOTER)


def test_a_file_the_branch_deleted_is_named_without_a_link(repo: Repo) -> None:
    repo.write("billing/old.py")
    repo.commit("on main")
    repo.branch("feature")
    repo.git("rm", "-q", "billing/old.py")
    repo.plan("reviewing", A)
    _conformant(repo, A, _block("billing/old.py"))
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["critical_files"] == [{"path": "billing/old.py", "link": None}]
    assert f"- `{A}`: `billing/old.py` (no longer on the branch)\n" in payload["body"]


@pytest.mark.parametrize("conformity", ["1. Proved.\n", _block()])
def test_without_a_block_or_with_an_empty_one_the_body_is_what_it_was(
    repo: Repo, conformity: str
) -> None:
    repo.branch("feature")
    repo.write("billing/pay.py")
    repo.plan("reviewing", A)
    _conformant(repo, A, conformity)
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["critical_files"] == []
    assert payload["body"] == (
        "## Plans on this branch\n"
        "\n"
        "| Plan | State | Blueprint | Plan |\n"
        "|---|---|---|---|\n"
        f"| `{A}` | conformant | [blueprint.md](docs/plans/{A}/blueprint.md)"
        f" | [plan.md](docs/plans/{A}/plan.md) |\n"
        "\n"
        f"{FOOTER}\n"
    )


def test_a_plan_that_is_not_conformant_yet_lists_no_file(repo: Repo) -> None:
    repo.branch("feature")
    repo.write("billing/pay.py")
    folder = repo.plan("reviewing", A)
    assert repo.run("record", A, *REVIEW).code == 0
    (folder / "conformity.md").write_text(_block("billing/pay.py"), encoding="utf-8")
    repo.commit("the work and its review, before the conformity is recorded")
    payload = repo.run("pr-body").json()
    assert payload["plans"][0]["state"] == "reviewing"
    assert payload["plans"][0]["critical_files"] == []
    assert CRITICAL_TITLE not in payload["body"]


def test_the_files_of_every_conformant_plan_are_listed_under_its_name(repo: Repo) -> None:
    repo.branch("feature")
    repo.write("billing/pay.py")
    repo.write("auth/token.py")
    repo.plan("reviewing", A)
    _conformant(repo, A, _block("billing/pay.py"))
    repo.plan("reviewing", B)
    _conformant(repo, B, _block("auth/token.py", "billing/pay.py"))
    repo.plan("executing", "2026-09-03-gamma")
    body = repo.run("pr-body").json()["body"]
    lines = [line for line in body.splitlines() if line.startswith("- `")]
    assert lines == [
        f"- `{A}`: [billing/pay.py](billing/pay.py)",
        f"- `{B}`: [auth/token.py](auth/token.py)",
        f"- `{B}`: [billing/pay.py](billing/pay.py)",
    ]


@pytest.mark.parametrize(
    ("broken", "error"),
    [
        ("```critical-files\nbilling/pay.py\n", "conformity.md: line 1: the critical-files block"),
        (None, "conformity.md cannot be read"),
    ],
)
def test_a_conformity_broken_after_the_record_stops_the_description(
    repo: Repo, broken: str | None, error: str
) -> None:
    repo.branch("feature")
    repo.write("billing/pay.py")
    repo.plan("reviewing", A)
    folder = _conformant(repo, A, _block("billing/pay.py"))
    if broken is None:
        (folder / "conformity.md").unlink()
    else:
        (folder / "conformity.md").write_text(broken, encoding="utf-8")
    result = repo.run("pr-body")
    assert result.code == 2
    assert error in result.json()["error"]
