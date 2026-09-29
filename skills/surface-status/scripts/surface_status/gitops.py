"""The git facts the script needs (ADR 0015 and 0016).

Everything here reads: the script never writes to a repository. Commands run in the project root
(`git -C`), so every path given or returned is relative to it, whether the project is the top of
the work tree or a folder inside it. No command touches the network or the working tree: the plans
of another branch are read from git objects (ADR 0016).
"""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT_SECONDS = 60
_ENV = {"GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
_ORIGIN = "origin/"
_GITHUB = re.compile(
    r"(?:https?://(?:[^/@]+@)?|ssh://git@|git@)github\.com[:/]"
    r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?"
)


class GitError(Exception):
    """A git fact that could not be established, with what the caller can do about it."""


@dataclass(frozen=True, slots=True)
class Commit:
    hash: str
    subject: str
    files: tuple[str, ...]


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # noqa: S603 (fixed argument list, no shell)
            ["git", "-C", str(root), *args],  # noqa: S607 (git is looked up on the PATH)
            capture_output=True,
            check=False,
            timeout=_TIMEOUT_SECONDS,
            env={**os.environ, **_ENV},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        message = f"git could not run: {error}"
        raise GitError(message) from error


def _try(root: Path, *args: str) -> str | None:
    """Return the stripped standard output of a command that may fail, None when it failed."""
    done = _run(root, *args)
    return done.stdout.decode("utf-8", errors="replace").strip() if done.returncode == 0 else None


def _must(root: Path, *args: str) -> bytes:
    done = _run(root, *args)
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", errors="replace").strip()
        message = f"git {' '.join(args[:2])} failed: {detail}"
        raise GitError(message)
    return done.stdout


def is_work_tree(root: Path) -> bool:
    try:
        return _try(root, "rev-parse", "--is-inside-work-tree") == "true"
    except GitError:
        return False


def _resolves(root: Path, ref: str) -> bool:
    return bool(_try(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"))


def main_ref(root: Path) -> str:
    """Name the main branch: `origin/HEAD`, else local `main`, `master`, else their `origin/` twins.

    A CI checkout of a pull request is detached and often shallow: it has no local branch and may
    have no `origin/HEAD`, but it does hold the remote branch (ADR 0015).
    """
    head = _try(root, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
    if head is not None and _resolves(root, head):
        return head
    for name in ("main", "master"):
        if _resolves(root, f"refs/heads/{name}"):
            return name
    for name in ("main", "master"):
        if _resolves(root, f"refs/remotes/origin/{name}"):
            return f"{_ORIGIN}{name}"
    message = (
        "cannot find the main branch (looked for origin/HEAD, main, master, origin/main "
        "and origin/master)"
    )
    raise GitError(message)


def local_name(ref: str) -> str:
    """Name the local branch that follows a main reference: `origin/main` gives `main`."""
    return ref.removeprefix(_ORIGIN)


def current_branch(root: Path) -> str | None:
    """Name the checked out branch, None on a detached HEAD."""
    return _try(root, "symbolic-ref", "-q", "--short", "HEAD")


def merge_base(root: Path, main: str, ref: str = "HEAD") -> str:
    found = _try(root, "merge-base", main, ref)
    if not found:
        message = (
            f"no merge base between {main} and {ref}: a shallow clone needs its full history "
            "(fetch-depth: 0 in a CI checkout)"
        )
        raise GitError(message)
    return found


def tree_folders(root: Path, ref: str, directory: str) -> frozenset[str]:
    """Name the folders directly under a directory of a commit; none if it does not exist."""
    out = _must(root, "ls-tree", "-z", ref, f"{directory.strip('/')}/")
    names: set[str] = set()
    for entry in out.decode("utf-8", errors="replace").split("\0"):
        meta, _, path = entry.partition("\t")
        if meta.split(" ")[1:2] == ["tree"]:
            names.add(path.rsplit("/", 1)[-1])
    return frozenset(names)


def read_blob(root: Path, ref: str, path: str) -> bytes | None:
    """Read a file at a commit, None if the commit has no such file."""
    done = _run(root, "cat-file", "blob", f"{ref}:./{path}")
    return done.stdout if done.returncode == 0 else None


def unmerged_branches(root: Path, main: str, *, skip: str | None) -> list[tuple[str, str]]:
    """List the branches main does not contain, as (name, reference), local ones first.

    A branch that exists both locally and on `origin` is listed once, as the local one.
    """
    out = _must(
        root,
        "for-each-ref",
        f"--no-merged={main}",
        "--format=%(refname)",
        "refs/heads",
        "refs/remotes",
    ).decode("utf-8", errors="replace")
    local: dict[str, str] = {}
    remote: dict[str, str] = {}
    for refname in out.splitlines():
        if refname.startswith("refs/heads/"):
            local[refname.removeprefix("refs/heads/")] = refname
        elif refname.startswith(f"refs/remotes/{_ORIGIN}"):
            name = refname.removeprefix(f"refs/remotes/{_ORIGIN}")
            if name != "HEAD":
                remote[name] = refname
    merged = {**remote, **local}
    return [(name, merged[name]) for name in sorted(merged) if name != skip]


def commits_of_branch(root: Path, main: str) -> list[Commit]:
    """List the commits HEAD has and main has not, oldest first, merges left out.

    A merge of main into the branch brings commits main already holds, and the merge commit
    itself is not the work of anyone: neither is listed. Paths are relative to the project root.
    """
    listing = _must(root, "rev-list", "--no-merges", "--reverse", "HEAD", "--not", main)
    commits: list[Commit] = []
    for name in listing.decode("utf-8").split():
        subject = _must(root, "log", "-1", "--format=%s", name).decode("utf-8").strip()
        touched = _must(
            root,
            "diff-tree",
            "-r",
            "--root",
            "--no-commit-id",
            "--relative",
            "--name-only",
            "-z",
            name,
        )
        files = tuple(
            path for path in touched.decode("utf-8", errors="replace").split("\0") if path
        )
        commits.append(Commit(name, subject, files))
    return commits


def web_url(root: Path) -> str | None:
    """Give the GitHub address of `origin`, None for any other remote."""
    remote = _try(root, "remote", "get-url", "origin")
    found = None if remote is None else _GITHUB.fullmatch(remote)
    return None if found is None else f"https://github.com/{found['owner']}/{found['repo']}"


def prefix(root: Path) -> str:
    """Give the project root's path inside the work tree, with a trailing slash (empty at top)."""
    return _try(root, "rev-parse", "--show-prefix") or ""
