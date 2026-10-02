"""`record conformant` in a real repository: the code `conformity.md` leaves the developer to read.

Which files a critical zone covers is the reviewer's reading. That the branch changed a file is a
fact of git, so the script checks it before the list reaches the pull request description.
"""

from pathlib import Path

import pytest
from cli_support import Project
from git_support import Repo, isolate_git

A = "2026-09-01-alpha"
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


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    isolate_git(monkeypatch)
    return Repo(tmp_path)


def conformity(*paths: str) -> str:
    """Write a proof of conformity whose critical-files block lists the paths."""
    block = "".join(f"{path}\n" for path in paths)
    return f"1. Proved by the tests.\n\n```critical-files\n{block}```\n"


def _reviewed(project: Project, *paths: str) -> Path:
    """Drive a plan to a clean review whose `conformity.md` lists the paths; nothing committed."""
    folder = project.reach("reviewing", A)
    assert project.record(A, *REVIEW).code == 0
    (folder / "conformity.md").write_text(conformity(*paths), encoding="utf-8")
    return folder


def _state(repo: Repo) -> str:
    return str(repo.run("show", A).json()["state"])


def test_the_files_the_branch_added_and_modified_are_accepted(repo: Repo) -> None:
    repo.write("billing/tax.py", "rate = 1\n")
    repo.commit("tax on main")
    repo.branch("feature")
    repo.write("billing/tax.py", "rate = 2\n")
    repo.write("billing/pay.py")
    _reviewed(repo.project, "billing/pay.py", "billing/tax.py")
    repo.commit("the work and its review")
    assert repo.run("record", A, *CONFORMANT).code == 0
    assert _state(repo) == "conformant"


def test_a_listed_file_the_branch_did_not_change_refuses_the_conformity(repo: Repo) -> None:
    repo.write("billing/tax.py")
    repo.commit("tax on main")
    repo.branch("feature")
    repo.write("billing/pay.py")
    _reviewed(repo.project, "billing/pay.py", "billing/tax.py", "billing/typo.py")
    repo.commit("the work and its review")
    before = repo.project.journal(A)
    refused = repo.run("record", A, *CONFORMANT)
    assert refused.code == 1
    assert refused.json()["refused"] == {
        "code": "critical-files",
        "reason": (
            "conformity.md: the critical-files block lists a file the branch did not change: "
            "billing/tax.py, billing/typo.py"
        ),
    }
    assert repo.project.journal(A) == before
    assert _state(repo) == "reviewing"
    text = repo.run("record", A, *CONFORMANT, as_json=False)
    assert text.err.startswith("refused conformant (critical-files): conformity.md: ")


def test_a_malformed_block_refuses_the_conformity_with_its_line(repo: Repo) -> None:
    repo.branch("feature")
    repo.write("billing/pay.py")
    folder = _reviewed(repo.project, "billing/pay.py")
    unclosed = "proof\n```critical-files\nbilling/pay.py\n"
    (folder / "conformity.md").write_text(unclosed, encoding="utf-8")
    repo.commit("the work and its review")
    refused = repo.run("record", A, *CONFORMANT).json()["refused"]
    assert refused["code"] == "critical-files"
    assert refused["reason"].startswith("conformity.md: line 2: the critical-files block is not")


def test_a_file_the_branch_deleted_or_moved_is_one_it_changed(repo: Repo) -> None:
    repo.write("billing/old.py", "a = 1\nb = 2\nc = 3\n")
    repo.write("billing/gone.py")
    repo.commit("on main")
    repo.branch("feature")
    repo.git("mv", "billing/old.py", "billing/new.py")
    repo.git("rm", "-q", "billing/gone.py")
    _reviewed(repo.project, "billing/old.py", "billing/new.py", "billing/gone.py")
    repo.commit("the work and its review")
    assert repo.run("record", A, *CONFORMANT).code == 0


def test_a_change_left_uncommitted_is_not_the_branch_s(repo: Repo) -> None:
    repo.branch("feature")
    _reviewed(repo.project, "billing/pay.py")
    repo.commit("the review")
    repo.write("billing/pay.py")
    refused = repo.run("record", A, *CONFORMANT)
    assert refused.code == 1
    assert refused.json()["refused"]["code"] == "critical-files"
    repo.commit("the work")
    assert repo.run("record", A, *CONFORMANT).code == 0


def test_a_file_main_changed_after_the_branch_left_it_is_not_the_branch_s(repo: Repo) -> None:
    repo.write("billing/tax.py", "rate = 1\n")
    repo.commit("tax on main")
    repo.branch("feature")
    _reviewed(repo.project, "billing/tax.py")
    repo.commit("the review")
    repo.switch("main")
    repo.write("billing/tax.py", "rate = 2\n")
    repo.commit("main moves on")
    repo.switch("feature")
    assert repo.run("record", A, *CONFORMANT).json()["refused"]["code"] == "critical-files"


def test_a_conformity_that_lists_nothing_asks_git_nothing(repo: Repo) -> None:
    """No main branch can be found here, which a list of files to check would trip on."""
    repo.branch("feature")
    repo.git("branch", "-D", "main")
    folder = repo.plan("reviewing", A)
    assert repo.run("record", A, *REVIEW).code == 0
    assert repo.run("record", A, *CONFORMANT).code == 0
    assert (folder / "conformity.md").read_text(encoding="utf-8") == "report\n"


def test_a_list_that_git_cannot_check_is_a_usage_error_not_an_acceptance(repo: Repo) -> None:
    repo.branch("feature")
    repo.git("branch", "-D", "main")
    repo.write("billing/pay.py")
    _reviewed(repo.project, "billing/pay.py")
    repo.commit("the work and its review")
    before = repo.project.journal(A)
    result = repo.run("record", A, *CONFORMANT)
    assert result.code == 2
    assert "cannot find the main branch" in result.json()["error"]
    assert repo.project.journal(A) == before


def test_in_a_project_inside_the_work_tree_the_paths_start_at_the_project_root(
    repo: Repo,
) -> None:
    app = Project(repo.root / "app")
    repo.branch("feature")
    repo.write("app/billing/pay.py")
    folder = _reviewed(app, "app/billing/pay.py")
    repo.commit("the work and its review")
    assert app.record(A, *CONFORMANT).json()["refused"]["code"] == "critical-files"
    (folder / "conformity.md").write_text(conformity("billing/pay.py"), encoding="utf-8")
    assert app.record(A, *CONFORMANT).code == 0
