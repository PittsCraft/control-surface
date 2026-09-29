"""The description of the pull request, from the state (ADR 0016).

It lists every plan of the branch with its state and the links to `overview.md` and `plan.md`,
and nothing else: the description is refreshed as a whole, never appended to.
"""

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from surface_status import gitops
from surface_status.plan_folder import PlanFolder
from surface_status.report import JSON_VERSION, Payload, hand_of, read_plan
from surface_status.resolve import BranchScope, branch_scope
from surface_status.settings import Settings

TITLE = "## Plans on this branch"
_UNSAFE_IN_URL = {" ": "%20", "#": "%23", "?": "%3F", "%": "%25"}


def _quoted(path: str) -> str:
    return "".join(_UNSAFE_IN_URL.get(char, char) for char in path)


def _link(root: Path, scope: BranchScope, repo_path: str, label: str) -> str | None:
    """Link a file of the branch, absolute on GitHub, else by its path from the repository."""
    if not (root / repo_path).is_file():
        return None
    inside = f"{gitops.prefix(root)}{repo_path}"
    web = gitops.web_url(root)
    if web is None or scope.branch is None:
        return f"[{label}]({_quoted(inside)})"
    return f"[{label}]({web}/blob/{_quoted(scope.branch)}/{_quoted(inside)})"


def _plan_row(root: Path, settings: Settings, scope: BranchScope, folder: PlanFolder) -> Payload:
    view = read_plan(folder)
    directory = PurePosixPath(settings.plans_dir) / folder.name
    return {
        "name": folder.name,
        "state": None if view.state is None else view.state.state.value,
        "hand": hand_of(view.state),
        "overview": _link(root, scope, (directory / "overview.md").as_posix(), "overview.md"),
        "plan": _link(root, scope, (directory / "plan.md").as_posix(), "plan.md"),
    }


def render(rows: Sequence[Payload]) -> str:
    lines = [
        TITLE,
        "",
        "| Plan | State | Overview | Plan |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| `{row['name']}` | {row['state'] or 'no event yet'} "
        f"| {row['overview'] or 'missing'} | {row['plan'] or 'missing'} |"
        for row in rows
    )
    lines.extend(["", "Refreshed by `surface-status pr-body`; edit the plans, not this text.", ""])
    return "\n".join(lines)


def describe(root: Path, settings: Settings) -> Payload | None:
    """Build the description of the branch; None when the branch holds no plan.

    Raises `GitError` outside a git work tree, and `UnreadableJournalError` for a journal that
    cannot be replayed.
    """
    scope = branch_scope(root, settings)
    if scope is None:
        message = f"{root} is not in a git work tree: a description is written for a branch"
        raise gitops.GitError(message)
    if not scope.folders:
        return None
    rows = [_plan_row(root, settings, scope, folder) for folder in scope.folders]
    return {
        "v": JSON_VERSION,
        "branch": scope.branch,
        "plans": rows,
        "body": render(rows),
    }
