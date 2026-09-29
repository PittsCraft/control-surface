"""Shared builders for the git tests: real repositories in temporary folders, no network.

A repository has `main` with one commit, plans are made through the command line as an agent would
(`Project.reach`), and every commit is made by `git` itself, so what the script reads is what a
host project would hold.
"""

import subprocess
from pathlib import Path

import pytest
from cli_support import PLAN, Project, Result

__all__ = ["PLAN", "Repo", "isolate_git"]

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def isolate_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the user's git configuration (signing, hooks, default branch) out of the tests."""
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)


class Repo:
    """A git work tree holding a project, on `main`, with one commit."""

    def __init__(self, root: Path, *, main: str = "main", origin: "Repo | None" = None) -> None:
        self.root = root
        self.main = main
        if origin is None:
            self.git("init", "-q", "-b", main)
            (root / "README.md").write_text("# host\n", encoding="utf-8")
            self.project = Project(root)
            self.commit("initial commit")
        else:
            origin.git("clone", "-q", str(origin.root), str(root), at=root.parent)
            self.project = Project.__new__(Project)
            self.project.root = root
            self.project.plans = root / "docs" / "plans"

    def git(self, *args: str, at: Path | None = None) -> str:
        done = subprocess.run(
            ["git", "-C", str(at or self.root), *args],  # noqa: S607 (git is looked up on the PATH)
            capture_output=True,
            check=False,
            text=True,
        )
        assert done.returncode == 0, (args, done.stderr)
        return done.stdout.strip()

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def branch(self, name: str) -> None:
        self.git("switch", "-q", "-c", name)

    def switch(self, name: str) -> None:
        self.git("switch", "-q", name)

    def merge(self, name: str) -> None:
        self.git("merge", "-q", "--no-ff", "-m", f"merge {name}", name)

    def write(self, relative: str, text: str = "content\n") -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def plan(self, state: str, name: str = PLAN) -> Path:
        """Make a plan and drive it to a state; nothing is committed."""
        self.project.plans.mkdir(parents=True, exist_ok=True)  # git drops the empty folder
        return self.project.reach(state, name)

    def run(self, *args: str, as_json: bool = True) -> Result:
        return self.project.run(*args, as_json=as_json)

    def resolve(self, command: str, *plan: str) -> Result:
        return self.run("resolve", "--for", command, *plan)

    def names(self) -> list[str]:
        """List the plans the list shows."""
        return [row["name"] for row in self.run().json()["plans"]]
