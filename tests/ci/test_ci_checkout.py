"""The conformity check in the checkout a CI makes (the guide, step 5).

A toy project gets the chain installed from this checkout, in clone mode, and its plans are built
with the state script. The project is then fetched into a repository shaped like the one
`actions/checkout` leaves: detached HEAD, no local branch, `origin/main` and the other remote
branches only. The CI runs this file as a job of its own (G2), and the gates run it too.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ".claude/skills/surface-status/scripts/surface-status"
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}
# The events that lead a plan of two files to each state, with the reports they point at.
REPORTS = ("checks/rev-01-01.md", "reviews/pass-01.md", "conformity.md")
IN_PROGRESS = (("plan-opened", ()), ("interview-closed", ()))
CONFORMANT = (
    *IN_PROGRESS,
    ("check-done", ("--report", "checks/rev-01-01.md", "--omissions", "0")),
    ("plan-drafted", ()),
    ("plan-approved", ()),
    ("slice-done", ("--slice", "1", "--gates", "lint")),
    (
        "review-done",
        ("--report", "reviews/pass-01.md", "--defects", "0", "--deviations", "0", "--breaks", "0"),
    ),
    ("conformant", ("--conformity", "conformity.md")),
)


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, check=False, text=True, cwd=cwd, env=ENV)


def ok(cwd: Path, *args: str) -> str:
    done = run(cwd, *args)
    assert done.returncode == 0, (args, done.stdout, done.stderr)
    return done.stdout


def build_plan(toy: Path, name: str, events: tuple[tuple[str, tuple[str, ...]], ...]) -> None:
    """Write the developer's files of a plan, then drive it with the state script."""
    folder = toy / "docs" / "plans" / name
    for report in REPORTS:
        (folder / report).parent.mkdir(parents=True, exist_ok=True)
        (folder / report).write_text("report\n", encoding="utf-8")
    (folder / "blueprint.md").write_text("# Blueprint\n", encoding="utf-8")
    (folder / "plan.md").write_text("<!-- slice:1 -->\n```gates\n```\n", encoding="utf-8")
    for event, arguments in events:
        ok(toy, SCRIPT, "record", f"docs/plans/{name}", event, *arguments)


@pytest.fixture(scope="module")
def remote(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a bare repository holding `main` and one branch per fixture plan, chain installed."""
    base = tmp_path_factory.mktemp("ci")
    toy = base / "toy"
    ok(base, "git", "init", "-q", "-b", "main", str(toy))
    (toy / "README.md").write_text("toy\n", encoding="utf-8")
    ok(toy, "git", "add", "-A")
    ok(toy, "git", "commit", "-q", "-m", "init")
    ok(toy, sys.executable, str(ROOT / "install.py"), ".")  # from a clone: the file is in ROOT
    ok(toy, "git", "add", "-A")
    ok(toy, "git", "commit", "-q", "-m", "install the chain")
    for branch, events in (("conformant", CONFORMANT), ("in-progress", IN_PROGRESS)):
        ok(toy, "git", "switch", "-q", "-c", branch, "main")
        build_plan(toy, "2026-09-29-feature", events)
        ok(toy, "git", "add", "-A")
        ok(toy, "git", "commit", "-q", "-m", f"plan: {branch}")
    bare = base / "remote.git"
    ok(base, "git", "init", "-q", "--bare", str(bare))
    ok(toy, "git", "push", "-q", bare.as_uri(), "main", "conformant", "in-progress")
    return bare


def checkout(remote: Path, branch: str, destination: Path, *, depth: int | None) -> Path:
    """Leave a repository the way `actions/checkout` does: detached, no local branch, remotes only.

    `depth` None is `fetch-depth: 0`, the full history of every branch.
    """
    ok(destination.parent, "git", "init", "-q", str(destination))
    ok(destination, "git", "remote", "add", "origin", remote.as_uri())
    fetch = ["git", "fetch", "-q", "--no-tags"]
    if depth is not None:
        fetch.append(f"--depth={depth}")
    ok(destination, *fetch, "origin", "+refs/heads/*:refs/remotes/origin/*")
    ok(destination, "git", "checkout", "-q", "--detach", f"origin/{branch}")
    assert ok(destination, "git", "for-each-ref", "refs/heads") == ""
    assert run(destination, "git", "symbolic-ref", "-q", "HEAD").returncode == 1
    return destination


def test_a_conformant_plan_passes_in_a_ci_checkout(remote: Path, tmp_path: Path) -> None:
    ci = checkout(remote, "conformant", tmp_path / "ci", depth=None)

    done = run(ci, SCRIPT, "check", "--require", "conformant")

    assert done.returncode == 0, done.stderr
    assert "check passed" in done.stdout


def test_a_plan_in_progress_fails_in_a_ci_checkout(remote: Path, tmp_path: Path) -> None:
    ci = checkout(remote, "in-progress", tmp_path / "ci", depth=None)

    done = run(ci, SCRIPT, "check", "--require", "conformant")

    assert done.returncode == 1, done.stderr
    assert "FAIL 2026-09-29-feature" in done.stderr
    assert "neither conformant nor abandoned" in done.stderr


def test_the_installation_is_intact_in_a_ci_checkout(remote: Path, tmp_path: Path) -> None:
    ci = checkout(remote, "conformant", tmp_path / "ci", depth=None)

    done = run(ci, sys.executable, str(ROOT / "install.py"), "--check", ".")

    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize("branch", ["conformant", "in-progress"])
def test_a_depth_one_checkout_is_refused_and_says_why(
    remote: Path, tmp_path: Path, branch: str
) -> None:
    ci = checkout(remote, branch, tmp_path / "ci", depth=1)

    done = run(ci, SCRIPT, "check", "--require", "conformant")

    assert done.returncode == 2
    assert "fetch-depth: 0" in done.stderr
