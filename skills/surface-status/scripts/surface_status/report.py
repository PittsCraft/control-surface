"""What the read only commands say: the plan list, `show` and `check`.

Each command builds a plain payload (JSON shaped, `"v": 1`), and a renderer turns the
same payload into text, so the two outputs cannot disagree.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from surface_status.events import Event, PlanApproved
from surface_status.guards import InvalidJournalError, fold
from surface_status.journal import JournalError, read_events
from surface_status.machine import PlanState, State
from surface_status.plan_folder import JOURNAL, PlanFolder
from surface_status.settings import Settings

JSON_VERSION = 1
REQUIRE_CONFORM = "conform"

Payload = dict[str, Any]

_HAND = {
    State.INTERVIEW: "developer",
    State.DRAFTING: "agents",
    State.AWAITING_APPROVAL: "developer",
    State.EXECUTING: "agents",
    State.REVIEWING: "agents",
    State.FIXING: "agents",
    State.PLAN_CHANGE_PROPOSED: "developer",
    State.BLOCKED: "developer",
    State.CONFORM: "nobody",
    State.ABANDONED: "nobody",
}

_ALARM = (
    "abandoned after its approval: the branch may carry code written under this plan that was"
    " never declared conform. The alarm stays even if that code was removed, since the script"
    " cannot see code. Remove it or merge knowingly: the check is an alarm, not a lock"
)


class UnreadableJournalError(Exception):
    """A journal that does not decode or does not replay, with what is wrong and where."""


@dataclass(frozen=True, slots=True)
class PlanView:
    """A plan folder and what its journal says."""

    folder: PlanFolder
    events: tuple[Event, ...]
    state: PlanState | None


def read_plan(folder: PlanFolder) -> PlanView:
    """Replay the journal of a plan folder; raises `UnreadableJournalError`."""
    try:
        events = tuple(read_events(folder.journal))
        return PlanView(folder, events, fold(events))
    except (JournalError, InvalidJournalError) as error:
        message = f"{folder.name}: {error}"
        raise UnreadableJournalError(message) from error


def discover(root: Path, settings: Settings) -> list[PlanFolder]:
    """List the plan folders under the plans directory: those that hold a journal, by name."""
    plans = root / settings.plans_dir
    if not plans.is_dir():
        return []
    return [
        PlanFolder(entry)
        for entry in sorted(plans.iterdir(), key=lambda item: item.name)
        if entry.is_dir() and (entry / JOURNAL).is_file()
    ]


def hand_of(state: PlanState | None) -> str:
    """Who has the hand in each state; the command opens a plan."""
    return "agents" if state is None else _HAND[state.state]


def _state_name(state: PlanState | None) -> str | None:
    return None if state is None else state.state.value


def next_step(state: PlanState | None) -> str:  # noqa: C901, PLR0911 (one arm per state)
    """Name the next step: what each command does depending on the state."""
    if state is None:
        return "surface-plan: open the plan (plan-opened)"
    match state.state:
        case State.INTERVIEW:
            return "surface-plan: resume the interview at the first unanswered question"
        case State.DRAFTING:
            return "surface-plan: resume at the missing step (cross-check, then draft)"
        case State.AWAITING_APPROVAL:
            return (
                "the developer decides: surface-plan takes an amendment, "
                "surface-execute approves and executes"
            )
        case State.EXECUTING:
            if state.suspicion is not None:
                return (
                    "surface-execute: a reviewer judges the break suspected during slice"
                    f" {state.suspicion.slice_}"
                )
            following = state.remaining[0] if state.remaining else None
            return f"surface-execute: launch slice {following}"
        case State.REVIEWING:
            return "surface-execute: run the gates, then review, or record conformity"
        case State.FIXING:
            return "surface-execute: launch the fix"
        case State.PLAN_CHANGE_PROPOSED:
            return "surface-plan: present the proposal, record the acceptance or the refusal"
        case State.BLOCKED:
            return (
                "the developer decides: surface-plan takes an instruction or an amendment, "
                "surface-execute resumes where the loop stopped"
            )
        case State.CONFORM | State.ABANDONED:
            return "none: the plan is over"


def plan_row(view: PlanView) -> Payload:
    return {
        "name": view.folder.name,
        "state": _state_name(view.state),
        "hand": hand_of(view.state),
    }


def list_payload(rows: Sequence[Payload]) -> Payload:
    return {"v": JSON_VERSION, "plans": list(rows)}


def error_row(name: str, message: str) -> Payload:
    return {"name": name, "state": None, "hand": None, "error": message}


def _approval_binds(state: PlanState) -> bool:
    """Whether the last approval still holds the work to its overview.

    It does from the approval to `conform`, a block during execution and a pending plan change
    included. It does not in planning, where a new revision is drawn, nor once abandoned.
    """
    match state.state:
        case State.EXECUTING | State.REVIEWING | State.FIXING | State.PLAN_CHANGE_PROPOSED:
            return True
        case State.CONFORM:
            return True
        case State.BLOCKED:
            return state.before_blocked in {State.EXECUTING, State.REVIEWING, State.FIXING}
        case _:
            return False


def overview_alarms(view: PlanView) -> list[Payload]:
    """Say when `overview.md` is not the one the developer approved, while that approval binds."""
    state = view.state
    if state is None or not _approval_binds(state):
        return []
    current = view.folder.overview_hash()
    if current is None:
        message = "overview.md is missing, its content cannot be the approved one"
        return [{"code": "overview-missing", "message": message}]
    if current != state.approved_overview:
        message = "overview.md differs from the one of the last plan-approved"
        return [{"code": "overview-changed", "message": message}]
    return []


def _suspicion(state: PlanState | None) -> Payload | None:
    """Give the break suspected during a slice that no reviewer judged yet, with its reason."""
    if state is None or state.suspicion is None:
        return None
    return {"slice": state.suspicion.slice_, "why": state.suspicion.why}


def _gates(state: PlanState | None) -> list[str] | None:
    """Return the gates of the last drafted revision, which `gate` runs once it is approved.

    None when no revision was drafted with its gates, such as a plan drafted before plans named
    them; an empty list when the plan says the project has none.
    """
    gates = None if state is None else state.drafted_gates
    return None if gates is None else list(gates)


def show_payload(view: PlanView, settings: Settings) -> Payload:
    state = view.state
    slices = {
        "declared": sorted(state.declared) if state else [],
        "done": sorted(state.done) if state else [],
        "remaining": list(state.remaining) if state else [],
    }
    return {
        "v": JSON_VERSION,
        "plan": view.folder.name,
        "state": _state_name(state),
        "hand": hand_of(state),
        "next_step": next_step(state),
        "slices": slices,
        "passes": {
            "planning": state.planning_passes if state else 0,
            "execution": state.execution_passes if state else 0,
            "ceiling": settings.max_autonomous_passes,
        },
        "gates": _gates(state),
        "pending_proposal": state.pending_proposal if state else None,
        "pending_suspicion": _suspicion(state),
        "last_event": view.events[-1].name if view.events else None,
        "alarms": overview_alarms(view),
        "settings": settings.to_dict(),
    }


def _problems_for_conform(view: PlanView) -> list[Payload]:
    """List what keeps a plan from satisfying `--require conform`."""
    state = view.state
    if state is not None and state.state is State.ABANDONED:
        if any(isinstance(event, PlanApproved) for event in view.events):
            return [{"code": "abandoned-after-approval", "message": _ALARM}]
        return []
    if state is None or state.state is not State.CONFORM:
        where = "no event yet" if state is None else state.state.value
        message = f"in progress ({where}): the plan is neither conform nor abandoned"
        return [{"code": "in-progress", "message": message}]
    return overview_alarms(view)


def check_plan(folder: PlanFolder, *, require: str | None) -> Payload:
    """Validate the journal of a plan, and with `require` the conformity it must hold."""
    try:
        view = read_plan(folder)
    except UnreadableJournalError as error:
        problems: list[Payload] = [{"code": "journal-unreadable", "message": str(error)}]
        return {"name": folder.name, "state": None, "ok": False, "problems": problems}
    problems = _problems_for_conform(view) if require == REQUIRE_CONFORM else []
    return {
        "name": folder.name,
        "state": _state_name(view.state),
        "ok": not problems,
        "problems": problems,
    }


def check_payload(results: Sequence[Payload], *, require: str | None) -> Payload:
    return {
        "v": JSON_VERSION,
        "ok": all(result["ok"] for result in results),
        "require": require,
        "plans": list(results),
    }


def has_unreadable(results: Sequence[Payload]) -> bool:
    return any(
        problem["code"] == "journal-unreadable"
        for result in results
        for problem in result["problems"]
    )


def render_list(payload: Payload) -> str:
    rows: list[Payload] = payload["plans"]
    if not rows:
        return "no plan\n"
    width = max(len(str(row["name"])) for row in rows)
    lines: list[str] = []
    for row in rows:
        if "error" in row:
            lines.append(f"{row['name']:<{width}}  unreadable: {row['error']}")
        else:
            state = row["state"] or "no event yet"
            lines.append(f"{row['name']:<{width}}  {state:<20}  hand: {row['hand']}")
    return "\n".join(lines) + "\n"


def _plain(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        entries = cast("dict[str, object]", value)
        return ", ".join(f"{key} {_plain(item)}" for key, item in entries.items())
    return str(value)


def render_show(payload: Payload) -> str:
    slices: dict[str, list[int]] = payload["slices"]
    passes: dict[str, int] = payload["passes"]
    settings: dict[str, object] = payload["settings"]

    def listed(numbers: list[int]) -> str:
        return ", ".join(str(number) for number in numbers) or "none"

    lines = [
        f"plan: {payload['plan']}",
        f"state: {payload['state'] or 'no event yet'} (hand: {payload['hand']})",
        f"next step: {payload['next_step']}",
        f"slices: done {listed(slices['done'])}; remaining {listed(slices['remaining'])}",
        (
            f"passes: planning {passes['planning']}, execution {passes['execution']},"
            f" ceiling {passes['ceiling']}"
        ),
    ]
    gates: list[str] | None = payload["gates"]
    if gates is None:
        lines.append("gates: not named by a drafted revision")
    else:
        lines.append(f"gates: {'; '.join(gates) or 'none'}")
    if payload["pending_proposal"] is not None:
        lines.append(f"pending proposal: {payload['pending_proposal']}")
    suspicion: Payload | None = payload["pending_suspicion"]
    if suspicion is not None:
        lines.append(f"suspected break: slice {suspicion['slice']}: {suspicion['why']}")
    alarms: list[Payload] = payload["alarms"]
    lines.extend(f"ALARM {alarm['code']}: {alarm['message']}" for alarm in alarms)
    lines.append("settings:")
    lines.extend(f"  {key}: {_plain(value)}" for key, value in settings.items())
    return "\n".join(lines) + "\n"


def render_check(payload: Payload) -> str:
    results: list[Payload] = payload["plans"]
    if not results:
        return "check passed: no plan to check\n"
    lines: list[str] = []
    for result in results:
        lines.append(f"{'ok  ' if result['ok'] else 'FAIL'} {result['name']}")
        lines.extend(
            f"       {problem['code']}: {problem['message']}" for problem in result["problems"]
        )
    lines.append("check passed" if payload["ok"] else "check failed")
    return "\n".join(lines) + "\n"
