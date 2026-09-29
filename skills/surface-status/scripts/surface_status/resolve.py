"""Finding the plan without guessing (ADR 0016).

The plans of a branch are the plan folders it adds against its merge base with the main branch:
nothing is stored, git computes it. A folder already on main, terminal or not, is never the
branch's plan, so the plans kept on main after earlier merges are neither resolved nor listed.
Outside a git work tree there is no branch, and every folder that holds a journal counts.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from surface_status import gitops
from surface_status.guards import InvalidJournalError, fold
from surface_status.journal import JournalError, parse_events
from surface_status.machine import PlanState, State
from surface_status.plan_folder import JOURNAL, PlanFolder
from surface_status.report import JSON_VERSION, Payload, discover, read_plan
from surface_status.settings import Settings

PLAN_COMMAND = "plan"
EXECUTE_COMMAND = "execute"
COMMANDS = (PLAN_COMMAND, EXECUTE_COMMAND)

# States each command accepts: what each command does depending on the state.
_PLAN_STATES = frozenset(
    {
        State.INTERVIEW,
        State.DRAFTING,
        State.AWAITING_APPROVAL,
        State.PLAN_CHANGE_PROPOSED,
        State.BLOCKED,
    }
)
_EXECUTE_STATES = frozenset(
    {State.AWAITING_APPROVAL, State.EXECUTING, State.REVIEWING, State.FIXING}
)
_EXECUTION_STATES = frozenset({State.EXECUTING, State.REVIEWING, State.FIXING})


def sees(command: str | None, state: PlanState | None) -> bool:
    """Whether a plan in this state is one the command acts on; None asks for any plan in progress.

    A journal with no event yet is a plan still to open, which only `surface-plan` sees.
    `surface-execute` sees `blocked` only when the loop stopped during the execution.
    """
    if state is None:
        return command in {None, PLAN_COMMAND}
    if state.terminal:
        return False
    match command:
        case None:
            return True
        case "plan":
            return state.state in _PLAN_STATES
        case "execute":
            if state.state is State.BLOCKED:
                return state.before_blocked in _EXECUTION_STATES
            return state.state in _EXECUTE_STATES
        case _:
            message = f"unknown command {command!r}"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Listed:
    """A plan of the branch, on disk."""

    folder: PlanFolder
    state: str | None  # None: the journal holds no event yet

    @property
    def name(self) -> str:
        return self.folder.name


@dataclass(frozen=True, slots=True)
class Elsewhere:
    """A plan in progress on an unmerged branch, seen from the main branch."""

    branch: str
    plan: str
    state: str | None
    error: str | None = None  # the journal could not be read from that branch

    @property
    def suggestion(self) -> str:
        return f"git switch {self.branch}"


@dataclass(frozen=True, slots=True)
class Resolution:
    """What `resolve` found: the plans that match, and what else was seen on the way."""

    branch: str | None  # None outside a git work tree or on a detached HEAD
    matching: tuple[Listed, ...]
    unmatched: tuple[Listed, ...]  # in progress on the branch, but not for this command
    elsewhere: tuple[Elsewhere, ...]  # only from the main branch

    @property
    def chosen(self) -> Listed | None:
        return self.matching[0] if len(self.matching) == 1 else None


@dataclass(frozen=True, slots=True)
class BranchScope:
    """The plan folders the branch adds, on disk, and how git found them."""

    branch: str | None
    main: str
    base: str
    folders: tuple[PlanFolder, ...]

    @property
    def on_main(self) -> bool:
        return self.branch == gitops.local_name(self.main)


def branch_scope(root: Path, settings: Settings) -> BranchScope | None:
    """Find the plan folders of the branch; None outside a git work tree.

    The folders are read from the work tree, so a plan opened and not yet committed counts. A
    folder the merge base already holds does not, whatever it says.
    """
    if not gitops.is_work_tree(root):
        return None
    main = gitops.main_ref(root)
    base = gitops.merge_base(root, main)
    known = gitops.tree_folders(root, base, settings.plans_dir)
    folders = tuple(folder for folder in discover(root, settings) if folder.name not in known)
    return BranchScope(gitops.current_branch(root), main, base, folders)


def branch_folders(root: Path, settings: Settings) -> list[PlanFolder]:
    """List the plan folders the list and the check work on: the branch's, else all of them."""
    scope = branch_scope(root, settings)
    return discover(root, settings) if scope is None else list(scope.folders)


def _elsewhere(
    root: Path, settings: Settings, scope: BranchScope, command: str | None
) -> tuple[Elsewhere, ...]:
    found: list[Elsewhere] = []
    for name, ref in gitops.unmerged_branches(root, scope.main, skip=scope.branch):
        try:
            base = gitops.merge_base(root, scope.main, ref)
        except gitops.GitError:
            continue  # unrelated history: it adds no plan to this project
        known = gitops.tree_folders(root, base, settings.plans_dir)
        for plan in sorted(gitops.tree_folders(root, ref, settings.plans_dir) - known):
            path = PurePosixPath(settings.plans_dir) / plan / JOURNAL
            data = gitops.read_blob(root, ref, path.as_posix())
            if data is None:
                continue
            try:
                state = fold(parse_events(data))
            except (JournalError, InvalidJournalError) as error:
                found.append(Elsewhere(name, plan, None, str(error)))
                continue
            if sees(command, state):
                found.append(Elsewhere(name, plan, None if state is None else state.state.value))
    return tuple(found)


def resolve(root: Path, settings: Settings, command: str | None) -> Resolution:
    """Sort the plans of the branch into those the command sees and the others.

    `command` is `plan`, `execute` or None for any plan in progress. From the main branch, the
    unmerged branches are scanned too. Raises `UnreadableJournalError` for a journal of the branch
    that cannot be replayed: nothing it says can be trusted.
    """
    scope = branch_scope(root, settings)
    folders = discover(root, settings) if scope is None else list(scope.folders)
    matching: list[Listed] = []
    unmatched: list[Listed] = []
    for folder in folders:
        state = read_plan(folder).state
        listed = Listed(folder, None if state is None else state.state.value)
        if sees(command, state):
            matching.append(listed)
        elif state is None or not state.terminal:
            unmatched.append(listed)
    elsewhere = (
        _elsewhere(root, settings, scope, command) if scope is not None and scope.on_main else ()
    )
    branch = None if scope is None else scope.branch
    return Resolution(branch, tuple(matching), tuple(unmatched), elsewhere)


def owners(files: tuple[str, ...], plans_dir: str) -> frozenset[str]:
    """Name the plans whose journal a commit touches: the plans it belongs to (ADR 0016)."""
    directory = PurePosixPath(plans_dir).parts
    names: set[str] = set()
    for file in files:
        parts = PurePosixPath(file).parts
        if len(parts) == len(directory) + 2 and parts[:-2] == directory and parts[-1] == JOURNAL:
            names.add(parts[-2])
    return frozenset(names)


def _entry(listed: Listed) -> Payload:
    return {"name": listed.name, "state": listed.state}


def _elsewhere_entry(found: Elsewhere) -> Payload:
    entry: Payload = {
        "branch": found.branch,
        "plan": found.plan,
        "state": found.state,
        "suggestion": found.suggestion,
    }
    if found.error is not None:
        entry["error"] = found.error
    return entry


def explicit_payload(command: str, folder: PlanFolder) -> Payload:
    """Answer for a plan the caller named: it wins, whatever its state."""
    return {
        "v": JSON_VERSION,
        "ok": True,
        "for": command,
        "outcome": "explicit",
        "plan": folder.name,
        "candidates": [],
        "other_plans": [],
        "elsewhere": [],
    }


def resolution_payload(command: str, found: Resolution) -> Payload:
    chosen = found.chosen
    outcome = "one" if chosen is not None else ("several" if found.matching else "none")
    return {
        "v": JSON_VERSION,
        "ok": chosen is not None,
        "for": command,
        "outcome": outcome,
        "branch": found.branch,
        "plan": None if chosen is None else chosen.name,
        "candidates": [_entry(listed) for listed in found.matching],
        "other_plans": [_entry(listed) for listed in found.unmatched],
        "elsewhere": [_elsewhere_entry(item) for item in found.elsewhere],
    }


def _plans(entries: Sequence[Payload]) -> str:
    return ", ".join(f"{entry['name']} ({entry['state'] or 'no event yet'})" for entry in entries)


def render_resolution(payload: Payload) -> str:
    """Text of the answer: the plan name alone when one plan was found, else what was seen."""
    if payload["ok"]:
        return f"{payload['plan']}\n"
    candidates: list[Payload] = payload["candidates"]
    where = payload["branch"] or "this project"
    if candidates:
        lines = [
            (
                f"several plans of {where} match surface-{payload['for']}: "
                f"{_plans(candidates)}; ask the developer which one"
            )
        ]
    else:
        lines = [f"no plan of {where} for surface-{payload['for']}"]
    others: list[Payload] = payload["other_plans"]
    if others:
        lines.append(f"in progress here, but not for this command: {_plans(others)}")
    for item in payload["elsewhere"]:
        what = f"unreadable: {item['error']}" if "error" in item else item["state"]
        lines.append(
            f"in progress on branch {item['branch']}: {item['plan']} ({what});"
            f" switch with `{item['suggestion']}`"
        )
    return "\n".join(lines) + "\n"


def commits_payload(
    plan: str, scope: BranchScope, commits: Sequence[gitops.Commit], plans_dir: str
) -> Payload:
    """Split the commits of the branch: those of the plan, and those that belong to no plan."""
    own: list[Payload] = []
    free: list[Payload] = []
    for commit in commits:
        belongs = owners(commit.files, plans_dir)
        row: Payload = {"hash": commit.hash, "subject": commit.subject}
        if plan in belongs:
            own.append(row)
        elif not belongs:
            free.append(row)
    return {
        "v": JSON_VERSION,
        "plan": plan,
        "main": scope.main,
        "base": scope.base,
        "commits": own,
        "unowned": free,
    }


def render_commits(payload: Payload) -> str:
    def listing(rows: list[Payload]) -> list[str]:
        return [f"  {row['hash'][:7]} {row['subject']}" for row in rows] or ["  none"]

    return "\n".join(
        [
            f"plan: {payload['plan']}",
            f"base: {payload['base']} (merge base with {payload['main']})",
            "commits of the plan:",
            *listing(payload["commits"]),
            "commits that belong to no plan:",
            *listing(payload["unowned"]),
            "",
        ]
    )
