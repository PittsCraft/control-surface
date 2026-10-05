#!/usr/bin/env python3
"""A stand-in for `gh`, the GitHub CLI, where the sessions of the tests have no GitHub to reach.

The toy project and the host of the evaluations push to a bare repository on disk, on which the
real `gh` opens no pull request. The image of `tests/e2e/Dockerfile` puts this script first on the
`PATH` under the name `gh`, so a session plays the pull request steps of the chain. It answers the
calls the prompts make as `gh` 2.78.0 does without a terminal, on the repository of the current
directory, keeps the pull requests it is asked for, and records every call:

    gh pr create --title <title> (--body <text> | --body-file <file or ->) [--draft]
    gh pr edit [<pull request>] [--title <title>] [--body <text> | --body-file <file or ->]
    gh pr list [--state <state>] [--author <login>] [--limit <n>] [--json <fields>]
    gh pr view [<pull request>] [--json <fields>]
    gh pr ready [<pull request>] [--undo]
    gh repo view [--json <fields>]
    gh auth status

Anything else gets an error that says so, and is recorded as not played. No call reaches a
network. `tests/e2e/README.md` says what the stand-in does not imitate.

What it keeps of a repository lives in its git directory, under `gh-stand-in/`: `pulls.json`, the
pull requests, and `calls.jsonl`, one line per call. The git directory is there for every
repository, with or without a remote, so every call has a place to be recorded. It belongs to one
repository, where several projects run at the same time in one container. And it is out of the
work tree, where the record would show in `git status`, could be committed, and would be met by a
session that explores the code.

The harness reads them with `pulls`, `pull_of` and `calls`. `open_pull` gives a prepared state the
pull request a session would have left, with no call recorded.
"""

import fcntl
import io
import json
import re
import subprocess
import sys
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, cast

IMITATES = "2.78.0"  # the version of `gh` whose answers were read
FOLDER = "gh-stand-in"  # in the git directory of the repository
PULLS = "pulls.json"
RECORD = "calls.jsonl"
LOCK = "lock"  # held by one call at a time
OWNER = "stand-in"  # owns every repository on the GitHub of the stand-in
LOGIN = "developer"  # opens every pull request there
AUTHOR: Mapping[str, object] = {"id": OWNER, "is_bot": False, "login": LOGIN, "name": "Developer"}
OPEN = "OPEN"
STATES = ("open", "closed", "merged", "all")
TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"  # the form GitHub gives, and the journal of a plan
PULL_FIELDS = (
    "author",
    "baseRefName",
    "body",
    "createdAt",
    "headRefName",
    "isDraft",
    "number",
    "state",
    "title",
    "updatedAt",
    "url",
)
REPOSITORY_FIELDS = ("defaultBranchRef", "description", "name", "nameWithOwner", "owner", "url")


@dataclass(frozen=True, slots=True)
class Pull:
    """A pull request, as the stand-in keeps it."""

    number: int
    head: str
    base: str
    title: str
    body: str
    draft: bool
    state: str  # OPEN, CLOSED or MERGED: no call closes or merges one
    created: str
    updated: str


@dataclass(frozen=True, slots=True)
class Call:
    """One call of `gh`, as the record keeps it."""

    at: str
    argv: tuple[str, ...]
    stdin: str | None  # what the call read on its standard input, None when it read nothing
    branch: str | None  # the branch checked out then
    command: str | None  # `pr edit`, None when the stand-in does not know the command
    played: bool  # False when the stand-in could not answer as `gh` would
    marks_ready: bool  # the call asks to mark a pull request ready for review
    pull: int | None  # the pull request it opened or changed
    body: str | None  # the description it gave, to a pull request it reached or not
    exit_code: int
    stdout: str
    stderr: str


class RefusedError(Exception):
    """A call `gh` refuses too, with the message it prints."""


class NotPlayedError(Exception):
    """A call the real `gh` may answer, and the stand-in does not."""


def _refuse(message: str) -> NoReturn:
    raise RefusedError(message)


def _not_played(what: str) -> NoReturn:
    message = (
        f"gh stand-in: {what} is not played here. This stand-in for the GitHub CLI answers:"
        f" {', '.join(_FLAGS)}. `gh --help` lists their flags."
    )
    raise NotPlayedError(message)


# What is kept of a repository, and how the harness reads it.


def store(repo: Path) -> Path:
    """Name the folder the stand-in keeps of a repository whose git directory is its `.git`."""
    return repo / ".git" / FOLDER


def pulls(repo: Path) -> list[Pull]:
    """Read the pull requests of a repository, in the order of their numbers."""
    return _read_pulls(store(repo))


def pull_of(repo: Path, branch: str) -> Pull | None:
    """Give the open pull request of a head branch, None when it has none."""
    return next((pull for pull in pulls(repo) if pull.state == OPEN and pull.head == branch), None)


def calls(repo: Path) -> list[Call]:
    """Read the record of a repository: every call made in it, in order."""
    record = store(repo) / RECORD
    if not record.is_file():
        return []
    found: list[Call] = []
    for line in record.read_text(encoding="utf-8").splitlines():
        try:
            held = cast("dict[str, Any]", json.loads(line))
            del held["v"]
            held["argv"] = tuple(held["argv"])
            found.append(Call(**held))
        except (ValueError, TypeError, KeyError):
            continue  # a line cut by the kill of a session
    return found


def open_pull(  # noqa: PLR0913 (what a pull request is made of, each by its name)
    repo: Path, *, head: str, base: str, title: str, body: str, draft: bool
) -> Pull:
    """Open a pull request with no call recorded, for a state a harness prepares."""
    kept = store(repo)
    with _locked(kept):
        held = _read_pulls(kept)
        opened = _new(held, head=head, base=base, title=title, body=body, draft=draft)
        _write_pulls(kept, [*held, opened])
    return opened


def _now() -> str:
    return datetime.now(UTC).strftime(TIMESTAMP)


def _new(  # noqa: PLR0913 (what a pull request is made of, each by its name)
    held: Sequence[Pull], *, head: str, base: str, title: str, body: str, draft: bool
) -> Pull:
    number = max((pull.number for pull in held), default=0) + 1
    now = _now()
    return Pull(number, head, base, title, body, draft, OPEN, created=now, updated=now)


def _read_pulls(kept: Path) -> list[Pull]:
    path = kept / PULLS
    if not path.is_file():
        return []
    held = cast("dict[str, list[dict[str, Any]]]", json.loads(path.read_text(encoding="utf-8")))
    return sorted((Pull(**pull) for pull in held["pulls"]), key=lambda pull: pull.number)


def _write_pulls(kept: Path, held: Sequence[Pull]) -> None:
    """Replace the file in one move, so that a reader never meets half of it."""
    text = json.dumps({"v": 1, "pulls": [asdict(pull) for pull in held]}, indent=2) + "\n"
    scratch = kept / f"{PULLS}.new"
    scratch.write_text(text, encoding="utf-8")
    scratch.replace(kept / PULLS)


def _append(kept: Path, call: Call) -> None:
    """Add a call to the record, on a line of its own even after one a kill cut short."""
    record = kept / RECORD
    written = record.read_bytes() if record.is_file() else b""
    line = json.dumps({"v": 1, **asdict(call)}, ensure_ascii=False)
    with record.open("a", encoding="utf-8") as out:
        out.write(f"{line}\n" if not written or written.endswith(b"\n") else f"\n{line}\n")


@contextmanager
def _locked(kept: Path) -> Generator[None]:
    """Hold the folder for one call: a session may run two `gh` at the same time."""
    kept.mkdir(parents=True, exist_ok=True)
    with (kept / LOCK).open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


# One call: the repository it is made in, and what it leaves.


def _git(*args: str) -> str | None:
    """Ask git in the current directory, None when it refuses."""
    done = subprocess.run(
        ["git", *args],  # noqa: S607 (git from the PATH, as `gh` runs it)
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def _has(ref: str) -> bool:
    return _git("rev-parse", "--verify", "--quiet", ref) is not None


@dataclass(slots=True)
class _Turn:
    """One call being answered: where it is made, the pull requests then, and what it leaves."""

    repository: str  # the name of the work tree, which names the repository on GitHub
    branch: str | None
    remote: str | None
    pulls: list[Pull] = field(default_factory=list[Pull])
    out: str = ""
    err: str = ""
    stdin: str | None = None
    pull: int | None = None
    body: str | None = None
    marks_ready: bool = False

    @property
    def slug(self) -> str:
        return f"{OWNER}/{self.repository}"

    @property
    def address(self) -> str:
        return f"https://github.com/{self.slug}"

    def address_of(self, pull: Pull) -> str:
        return f"{self.address}/pull/{pull.number}"

    def keep(self, pull: Pull) -> None:
        """Hold a pull request the call opened or changed."""
        self.pulls = [*(held for held in self.pulls if held.number != pull.number), pull]
        self.pull = pull.number

    def needs_remote(self) -> str:
        if self.remote is None:
            _refuse("no git remotes found")
        return self.remote

    def needs_branch(self, told: str = "") -> str:
        if self.branch is None:
            _refuse(f"{told}failed to run git: not on any branch")
        return self.branch


def _turn(kept: Path) -> _Turn:
    top = _git("rev-parse", "--show-toplevel")
    remotes = (_git("remote") or "").split()
    return _Turn(
        repository=Path(top).name if top else kept.parent.stem,
        branch=_git("symbolic-ref", "--quiet", "--short", "HEAD"),
        remote="origin" if "origin" in remotes else next(iter(remotes), None),
    )


# The arguments of a call.


@dataclass(frozen=True, slots=True)
class _Flag:
    name: str
    short: str | None = None
    value: bool = True  # False for a switch, which takes none
    many: bool = False  # given several times, its values add up


_JSON = (_Flag("json", many=True), _Flag("jq", "q"))
_FLAGS: Mapping[str, tuple[_Flag, ...]] = {
    "pr create": (
        _Flag("draft", "d", value=False),
        _Flag("title", "t"),
        _Flag("body", "b"),
        _Flag("body-file", "F"),
        _Flag("base", "B"),
        _Flag("head", "H"),
    ),
    "pr edit": (
        _Flag("title", "t"),
        _Flag("body", "b"),
        _Flag("body-file", "F"),
        _Flag("base", "B"),
    ),
    "pr list": (
        _Flag("state", "s"),
        _Flag("limit", "L"),
        _Flag("author", "A"),
        _Flag("head", "H"),
        _Flag("base", "B"),
        _Flag("draft", "d", value=False),
        *_JSON,
    ),
    "pr view": _JSON,
    "pr ready": (_Flag("undo", value=False),),
    "repo view": _JSON,
    "auth status": (_Flag("hostname", "h"), _Flag("active", "a", value=False)),
}
_JQ_STEP = re.compile(r"\.?\[(?P<index>-?[0-9]*)\]|\.(?P<key>[A-Za-z_][A-Za-z0-9_]*)")
_NUMBER = re.compile(r"#?(?P<number>[0-9]+)|https?://\S+/pull/(?P<linked>[0-9]+)\S*")


def _usage() -> str:
    opening = (
        f"A stand-in for gh {IMITATES}, the GitHub CLI: it keeps the pull requests of this"
        " repository in its git directory and reaches no network."
    )
    lines = [opening, ""]
    for command, flags in _FLAGS.items():
        shown = (f"[--{flag.name}{' <value>' if flag.value else ''}]" for flag in flags)
        lines.append("  " + " ".join(["gh", command, *shown]))
    return "\n".join(lines) + "\n"


def _parse(command: str, args: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """Split the arguments of a command into its flags and the rest, as `gh` reads them."""
    known = _FLAGS[command]
    given: dict[str, str] = {}
    rest: list[str] = []
    queue = list(args)
    while queue:
        arg = queue.pop(0)
        if arg == "--":
            return given, rest + queue
        if arg == "-" or not arg.startswith("-"):
            rest.append(arg)
            continue
        if arg.startswith("--"):
            name, attached, value = arg[2:].partition("=")
            flag = next((flag for flag in known if flag.name == name), None)
        else:
            attached, value = arg[2:], arg[2:].removeprefix("=")
            flag = next((flag for flag in known if flag.short == arg[1]), None)
            if flag is not None and not flag.value and attached and attached == value:
                # Short flags written together, as in `-dt <title>`: the others are read next.
                queue.insert(0, f"-{attached}")
                attached = value = ""
        if flag is None:
            _not_played(f"the flag {arg.partition('=')[0]} of `gh {command}`")
        if not flag.value:
            value = value if attached else "true"
        elif not attached:
            if not queue:
                _refuse(_needs_an_argument(command, flag))
            value = queue.pop(0)
        given[flag.name] = (
            f"{given[flag.name]},{value}" if flag.many and flag.name in given else value
        )
    return given, rest


def _needs_an_argument(command: str, flag: _Flag) -> str:
    if flag.name != "json":
        return f"flag needs an argument: --{flag.name}"
    fields = REPOSITORY_FIELDS if command == "repo view" else PULL_FIELDS
    listing = "\n  ".join(fields)
    return f"Specify one or more comma-separated fields for `--json`:\n  {listing}"


def _on(given: Mapping[str, str], switch: str) -> bool:
    return given.get(switch, "false").lower() not in {"false", "0", "f"}


def _describe(turn: _Turn, given: Mapping[str, str], *, exclusive: bool) -> None:
    """Read the description a call gives: its flag, a file or the standard input."""
    source = given.get("body-file")
    if source is None:
        turn.body = given.get("body")
    elif exclusive and "body" in given:
        _refuse("specify only one of `--body` or `--body-file`")
    elif source == "-":
        turn.body = turn.stdin = sys.stdin.read()
    else:
        try:
            turn.body = Path(source).read_text(encoding="utf-8")
        except OSError as error:
            _refuse(f"open {source}: {(error.strerror or 'unreadable').lower()}")


def _found(turn: _Turn, rest: Sequence[str]) -> Pull:
    """Find the pull request a call names, by number, address or branch, else the branch's own."""
    if len(rest) > 1:
        _refuse(f"accepts at most 1 arg(s), received {len(rest)}")
    turn.needs_remote()
    named = _NUMBER.fullmatch(rest[0]) if rest else None
    if named is not None:
        number = int(named["number"] or named["linked"])
        for pull in turn.pulls:
            if pull.number == number:
                return pull
        _refuse(
            f"GraphQL: Could not resolve to a PullRequest with the number of {number}."
            " (repository.pullRequest)"
        )
    branch = rest[0] if rest else turn.needs_branch()
    # An open one first, then the last one closed, as `gh` picks.
    held = sorted(
        (pull for pull in turn.pulls if pull.head == branch),
        key=lambda pull: (pull.state != OPEN, -pull.number),
    )
    if not held:
        _refuse(f'no pull requests found for branch "{branch}"')
    return held[0]


# What `--json` and `--jq` print.


def _compact(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fields(
    given: Mapping[str, str], known: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    """Keep the fields `--json` asks of each row."""
    asked = [name for name in given["json"].split(",") if name]
    for name in asked:
        if name not in known:
            listing = "\n  ".join(known)
            message = f'Unknown JSON field: "{name}"\nAvailable fields:\n  {listing}'
            raise NotPlayedError(message)
    return [{name: row[name] for name in asked} for row in rows]


def _printed(given: Mapping[str, str], value: object) -> str:
    """Print a value as `gh` does without a terminal: on one line, or through `--jq`."""
    if "jq" not in given:
        return f"{_compact(value)}\n"
    found = _jq(value, given["jq"])
    return "".join(f"{one if isinstance(one, str) else _compact(one)}\n" for one in found)


def _jq(value: object, expression: str) -> list[object]:
    """Follow the paths of a jq expression, such as `.[].headRefName`: all of jq played here."""
    values = [value]
    for stage in expression.split("|"):
        path = stage.strip()
        position = 1 if path == "." else 0
        while position < len(path):
            step = _JQ_STEP.match(path, position)
            if step is None:
                break
            values = [found for held in values for found in _jq_step(held, step)]
            position = step.end()
        if not path or position < len(path):
            _not_played(f"a `--jq` that is more than a path, such as `{expression}`,")
    return values


def _jq_step(held: object, step: re.Match[str]) -> list[object]:
    key, index = cast("str | None", step["key"]), cast("str | None", step["index"])
    if key is not None and held is None:
        return [None]
    if key is not None and isinstance(held, dict):
        return [cast("dict[str, object]", held).get(key)]
    if key is None and isinstance(held, list):
        items = cast("list[object]", held)
        if not index:
            return items
        return [items[int(index)] if -len(items) <= int(index) < len(items) else None]
    _not_played("a `--jq` path that does not fit what `--json` gives")


def _jq_needs_json(given: Mapping[str, str]) -> None:
    if "jq" in given and "json" not in given:
        _refuse("cannot use `--jq` without specifying `--json`")


# The commands.


def _pull_fields(turn: _Turn, pull: Pull) -> dict[str, object]:
    return {
        "author": AUTHOR,
        "baseRefName": pull.base,
        "body": pull.body,
        "createdAt": pull.created,
        "headRefName": pull.head,
        "isDraft": pull.draft,
        "number": pull.number,
        "state": pull.state,
        "title": pull.title,
        "updatedAt": pull.updated,
        "url": turn.address_of(pull),
    }


def _default_branch(remote: str) -> str:
    """Name the branch a pull request merges into when none is given: the main one."""
    head = _git("symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD")
    if head is not None:
        return head.removeprefix(f"{remote}/")
    return "master" if _has(f"refs/remotes/{remote}/master") else "main"


def _pushed_branch(turn: _Turn, remote: str) -> str:
    """Name the current branch, the head once the remote holds its last commit."""
    changes = len((_git("status", "--porcelain") or "").splitlines())
    if changes:
        turn.err += f"Warning: {changes} uncommitted change{'s' if changes > 1 else ''}\n"
    branch = turn.needs_branch("could not determine the current branch: ")
    pushed = _git("rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}")
    if pushed is None or pushed != _git("rev-parse", "HEAD"):
        _refuse(
            "aborted: you must first push the current branch to a remote, or use the --head flag"
        )
    return branch


def _create(turn: _Turn, given: Mapping[str, str], _rest: Sequence[str]) -> None:
    body = turn.body
    if "title" not in given or body is None:
        _refuse(
            "must provide `--title` and `--body` (or `--fill` or `fill-first` or `--fillverbose`)"
            " when not running interactively"
        )
    remote = turn.needs_remote()
    base = given.get("base") or _default_branch(remote)
    head = given.get("head") or _pushed_branch(turn, remote)
    for pull in turn.pulls:
        if pull.state == OPEN and (pull.head, pull.base) == (head, base):
            _refuse(
                f'a pull request for branch "{head}" into branch "{base}" already exists:\n'
                f"{turn.address_of(pull)}"
            )
    if not given["title"].strip():
        _refuse("pull request title must not be blank")
    ahead = _git(
        "rev-list", "--count", f"refs/remotes/{remote}/{base}..refs/remotes/{remote}/{head}"
    )
    if ahead is None:
        _refuse(
            "pull request create failed: GraphQL: Head sha can't be blank, Base sha can't be blank,"
            f" No commits between {base} and {head}, Head ref must be a branch (createPullRequest)"
        )
    if ahead == "0":
        _refuse(
            f"pull request create failed: GraphQL: No commits between {base} and {head}"
            " (createPullRequest)"
        )
    opened = _new(
        turn.pulls, head=head, base=base, title=given["title"], body=body, draft=_on(given, "draft")
    )
    turn.keep(opened)
    turn.out = f"{turn.address_of(opened)}\n"


def _edit(turn: _Turn, given: Mapping[str, str], rest: Sequence[str]) -> None:
    body = turn.body
    if body is None and "title" not in given and "base" not in given:
        # The misspelt flag is the message of `gh` itself.
        _refuse(
            "--tile, --body, --reviewer, --assignee, --label, --project, or --milestone required"
            " when not running interactively"
        )
    pull = _found(turn, rest)
    edited = replace(
        pull,
        title=given.get("title", pull.title),
        body=pull.body if body is None else body,
        base=given.get("base", pull.base),
        updated=_now(),
    )
    turn.keep(edited)
    turn.out = f"{turn.address_of(edited)}\n"


def _ready(turn: _Turn, given: Mapping[str, str], rest: Sequence[str]) -> None:
    undo = _on(given, "undo")
    pull = _found(turn, rest)
    name = f"Pull request {turn.slug}#{pull.number}"
    if pull.state != OPEN:
        _refuse(f'X {name} is closed. Only draft pull requests can be marked as "ready for review"')
    if pull.draft == undo:
        turn.err += f'! {name} is already "{"in draft" if undo else "ready for review"}"\n'
        return
    turn.keep(replace(pull, draft=undo, updated=_now()))
    done = 'converted to "draft"' if undo else 'marked as "ready for review"'
    turn.err += f"\N{CHECK MARK} {name} is {done}\n"


def _shown_state(pull: Pull) -> str:
    return "DRAFT" if pull.draft and pull.state == OPEN else pull.state


def _list(turn: _Turn, given: Mapping[str, str], _rest: Sequence[str]) -> None:
    state = given.get("state", "open").lower()
    if state not in STATES:
        _refuse(
            f'invalid argument "{given["state"]}" for "-s, --state" flag:'
            " valid values are {open|closed|merged|all}"
        )
    limit = given.get("limit", "30")
    if not limit.isdecimal() or int(limit) < 1:
        _refuse(f"invalid value for --limit: {limit}")
    _jq_needs_json(given)
    turn.needs_remote()
    found = [
        pull
        for pull in sorted(turn.pulls, key=lambda pull: -pull.number)
        if state in {"all", pull.state.lower()}
        and given.get("head", pull.head) == pull.head
        and given.get("base", pull.base) == pull.base
        and given.get("author", "@me") in {"@me", LOGIN}
        and ("draft" not in given or _on(given, "draft") == pull.draft)
    ][: int(limit)]
    if "json" in given:
        rows = [_pull_fields(turn, pull) for pull in found]
        turn.out = _printed(given, _fields(given, PULL_FIELDS, rows))
        return
    turn.out = "".join(
        f"{pull.number}\t{pull.title}\t{pull.head}\t{_shown_state(pull)}\t{pull.created}\n"
        for pull in found
    )


def _view(turn: _Turn, given: Mapping[str, str], rest: Sequence[str]) -> None:
    _jq_needs_json(given)
    pull = _found(turn, rest)
    if "json" in given:
        (row,) = _fields(given, PULL_FIELDS, [_pull_fields(turn, pull)])
        turn.out = _printed(given, row)
        return
    lines = {
        "title": pull.title,
        "state": _shown_state(pull),
        "author": LOGIN,
        "labels": "",
        "assignees": "",
        "reviewers": "",
        "projects": "",
        "milestone": "",
        "number": pull.number,
        "url": turn.address_of(pull),
        "auto-merge": "disabled",
    }
    shown = "".join(f"{key}:\t{value}\n" for key, value in lines.items())
    turn.out = f"{shown}--\n{pull.body}\n"


def _repo_view(turn: _Turn, given: Mapping[str, str], rest: Sequence[str]) -> None:
    if rest:
        _not_played("a repository other than that of the current directory")
    _jq_needs_json(given)
    remote = turn.needs_remote()
    if "json" not in given:
        turn.out = f"name:\t{turn.slug}\ndescription:\t\n"
        return
    fields: dict[str, object] = {
        "defaultBranchRef": {"name": _default_branch(remote)},
        "description": "",
        "name": turn.repository,
        "nameWithOwner": turn.slug,
        "owner": {"id": OWNER, "login": OWNER},
        "url": turn.address,
    }
    (row,) = _fields(given, REPOSITORY_FIELDS, [fields])
    turn.out = _printed(given, row)


def _auth_status(turn: _Turn, _given: Mapping[str, str], _rest: Sequence[str]) -> None:
    turn.out = (
        "github.com\n"
        f"  \N{CHECK MARK} Logged in to github.com account {LOGIN} (stand-in)\n"
        "  - Active account: true\n"
    )


_PLAYS: Mapping[str, Callable[[_Turn, Mapping[str, str], Sequence[str]], None]] = {
    "pr create": _create,
    "pr edit": _edit,
    "pr list": _list,
    "pr view": _view,
    "pr ready": _ready,
    "repo view": _repo_view,
    "auth status": _auth_status,
}
_TAKES_NO_ARGUMENT = frozenset({"pr create", "pr list", "auth status"})
_HELP = "help"
_VERSION = "version"


def _command(args: Sequence[str]) -> str | None:
    """Name the command a call asks for, None when the stand-in does not know it."""
    if not args or "--help" in args:
        return _HELP
    if args[0] in {"--version", _VERSION}:
        return _VERSION
    command = " ".join(args[:2])
    return command if command in _FLAGS else None


def _asks(
    turn: _Turn, command: str | None, args: Sequence[str]
) -> tuple[dict[str, str], list[str]]:
    """Read what a call asks, its description included, before the folder is held.

    A call fed by another, as in `gh pr view | gh pr edit --body-file -`, would otherwise wait
    for its standard input while the call that feeds it waits for the folder.
    """
    if command is None:
        _not_played(f"`gh {' '.join(args[:2])}`")
    if command in {_HELP, _VERSION}:
        return {}, []
    # A call that cannot even be read still asked to mark a pull request ready.
    turn.marks_ready = command == "pr ready"
    given, rest = _parse(command, args[2:])
    turn.marks_ready = command == "pr ready" and not _on(given, "undo")
    if rest and command in _TAKES_NO_ARGUMENT:
        _refuse(f'unknown argument "{rest[0]}"; please quote all values that have spaces')
    if command in {"pr create", "pr edit"}:
        _describe(turn, given, exclusive=command == "pr edit")
    return given, rest


def _play(
    kept: Path, turn: _Turn, command: str, given: Mapping[str, str], rest: Sequence[str]
) -> None:
    """Play a call on the pull requests of the folder, which the caller holds."""
    if command == _HELP:
        turn.out = _usage()
    elif command == _VERSION:
        turn.out = f"gh version {IMITATES} (stand-in)\n"
    else:
        turn.pulls = held = _read_pulls(kept)
        _PLAYS[command](turn, given, rest)
        if turn.pulls is not held:
            _write_pulls(kept, sorted(turn.pulls, key=lambda pull: pull.number))


def _told(turn: _Turn, args: Sequence[str], command: str | None, failure: Exception | None) -> Call:
    """Tell a call as the record keeps it, with what stopped it when something did."""
    played = failure is None or isinstance(failure, RefusedError)
    if failure is not None:
        known = isinstance(failure, RefusedError | NotPlayedError)
        turn.err += f"{failure}\n" if known else f"gh stand-in: failed on its own: {failure!r}\n"
        turn.out, turn.pull = "", None
    return Call(
        at=_now(),
        argv=tuple(args),
        stdin=turn.stdin,
        branch=turn.branch,
        command=command,
        played=played,
        marks_ready=turn.marks_ready,
        pull=turn.pull,
        body=turn.body,
        exit_code=0 if failure is None else 1,
        stdout=turn.out,
        stderr=turn.err,
    )


def _answer(kept: Path, turn: _Turn, args: Sequence[str]) -> Call:
    """Answer one call, keep what it changed, and add it to the record."""
    command = _command(args)
    asked: tuple[dict[str, str], list[str]] | None = None
    failure: Exception | None = None
    try:
        asked = _asks(turn, command, args)
    except Exception as error:  # noqa: BLE001 (a fault of the stand-in must reach the record)
        failure = error
    with _locked(kept):
        if asked is not None and command is not None:
            try:
                _play(kept, turn, command, *asked)
            except Exception as error:  # noqa: BLE001 (the same)
                failure = error
        call = _told(turn, args, command, failure)
        _append(kept, call)
    return call


def _unkept(args: Sequence[str], why: str) -> int:
    """Answer where nothing can be kept, outside a repository for one: the version, the help."""
    command = _command(args)
    if command not in {_HELP, _VERSION}:
        sys.stderr.write(f"{why}\n")
        return 1
    turn = _Turn(repository="", branch=None, remote=None)
    _play(Path(), turn, command, {}, [])
    sys.stdout.write(turn.out)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    common = _git("rev-parse", "--git-common-dir")
    if common is None:
        return _unkept(
            args,
            "failed to run git: fatal: not a git repository (or any of the parent directories):"
            " .git",
        )
    kept = Path(common).resolve() / FOLDER
    try:
        call = _answer(kept, _turn(kept), args)
    except OSError as error:
        return _unkept(args, f"gh stand-in: nothing can be kept in {kept}: {error.strerror}")
    sys.stdout.write(call.stdout)
    sys.stderr.write(call.stderr)
    return call.exit_code


if __name__ == "__main__":
    sys.exit(main())
