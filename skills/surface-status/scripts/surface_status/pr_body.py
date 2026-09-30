"""The description of the pull request, from the state (ADR 0016).

It lists every plan of the branch with its state and the links to `overview.md` and `plan.md`,
then the decisions agents took within the contract, which the developer did not see go by: the
plan amendments and the dismissed suspected breaks, one line each, for information. Nothing else:
the description is refreshed as a whole, never appended to.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from surface_status import gitops
from surface_status.events import (
    BreakSuspected,
    Event,
    PlanAmended,
    PlanChangeProposed,
    SuspicionDismissed,
)
from surface_status.plan_folder import PlanFolder
from surface_status.report import JSON_VERSION, Payload, hand_of, read_plan
from surface_status.resolve import BranchScope, branch_scope
from surface_status.settings import Settings

TITLE = "## Plans on this branch"
DECISIONS_TITLE = "### Decisions the agents took within the contract"
DECISIONS_NOTE = "For information: none of them changes the approved overview."
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


@dataclass(frozen=True, slots=True)
class Decision:
    """A decision an agent took within the contract, as the journal holds it.

    `why` is the reason on one line: the executor's, for an amendment or for the break a reviewer
    dismissed; None for a dismissal whose suspicion the journal never recorded. `note` is the
    reviewer's note of a dismissal, relative to the plan folder.
    """

    event: str
    slice_: int
    why: str | None
    note: str | None


def _one_line(text: str) -> str:
    return " ".join(text.split())


def decisions(events: Sequence[Event]) -> list[Decision]:
    """List the plan amendments and the dismissed suspicions of a journal, in its order."""
    found: list[Decision] = []
    suspected: BreakSuspected | None = None
    for event in events:
        match event:
            case PlanAmended():
                found.append(Decision(event.name, event.slice_, _one_line(event.why), None))
            case BreakSuspected():
                suspected = event
            case SuspicionDismissed():
                why = None
                if suspected is not None and suspected.slice_ == event.slice_:
                    why = _one_line(suspected.why)
                found.append(Decision(event.name, event.slice_, why, event.report))
                suspected = None
            case PlanChangeProposed():
                suspected = None
            case _:
                pass
    return found


def _decision_item(
    root: Path, scope: BranchScope, directory: PurePosixPath, decision: Decision
) -> Payload:
    note = None
    if decision.note is not None:
        note = _link(root, scope, (directory / decision.note).as_posix(), decision.note)
    return {"event": decision.event, "slice": decision.slice_, "why": decision.why, "note": note}


def _plan_row(root: Path, settings: Settings, scope: BranchScope, folder: PlanFolder) -> Payload:
    view = read_plan(folder)
    directory = PurePosixPath(settings.plans_dir) / folder.name
    return {
        "name": folder.name,
        "state": None if view.state is None else view.state.state.value,
        "hand": hand_of(view.state),
        "overview": _link(root, scope, (directory / "overview.md").as_posix(), "overview.md"),
        "plan": _link(root, scope, (directory / "plan.md").as_posix(), "plan.md"),
        "decisions": [
            _decision_item(root, scope, directory, decision) for decision in decisions(view.events)
        ],
    }


def _decision_line(name: str, item: Payload) -> str:
    head = f"- `{name}`, slice {item['slice']}"
    if item["event"] == PlanAmended.name:
        return f"{head}: plan amended: {item['why']}"
    reason = "" if item["why"] is None else f": {item['why']}"
    note = item["note"] or "missing"
    return f"{head}: suspected break dismissed by a reviewer{reason} (note: {note})"


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
    listed = [_decision_line(row["name"], item) for row in rows for item in row["decisions"]]
    if listed:
        lines.extend(["", DECISIONS_TITLE, "", DECISIONS_NOTE, "", *listed])
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
