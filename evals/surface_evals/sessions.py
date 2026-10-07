"""Real sessions, and what their streams say: the chain's own, and the calls of a single model.

A session of the chain is the headless session of the end to end tests (ADR 0025): it bypasses
permissions, so it runs in their container only. A model call, for the developer of an interview
or for the judge, is a session too, with its own system prompt and the tools it is given.
"""

import json
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import toy

POLL = 2  # seconds between two looks at a running session


@dataclass(frozen=True, slots=True)
class Launch:
    """An agent a session launched, and the model it was given."""

    agent: str
    model: str | None


@dataclass(frozen=True, slots=True)
class Gauge:
    """A reading of the weekly use of the subscription, and the week it belongs to."""

    used: float  # from 0 to 1
    week: float | None  # when that week ends, as the stream dates it, None when it does not


@dataclass(frozen=True, slots=True)
class SessionLog:
    """What the stream of a session says, read after it ended or was killed."""

    path: Path
    session_id: str | None
    ended: bool  # the stream closes with a result: the session was not killed
    final: str  # its final message
    cost: float  # USD at list price, summed over the session since its first launch
    gauges: tuple[Gauge, ...]  # the weekly use of the subscription, as it went
    launches: tuple[Launch, ...]


def _events(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("{"):
            try:
                events.append(cast("dict[str, object]", json.loads(raw)))
            except ValueError:
                continue  # a line cut by a kill
    return events


def _get(holder: object, key: str) -> object:
    """Read a key of what a stream holds, None when it is not an object or lacks the key."""
    return cast("dict[str, object]", holder).get(key) if isinstance(holder, dict) else None


def _tool_uses(event: dict[str, object]) -> list[dict[str, object]]:
    content = _get(event.get("message"), "content")
    blocks = cast("list[object]", content) if isinstance(content, list) else []
    return [
        cast("dict[str, object]", block) for block in blocks if _get(block, "type") == "tool_use"
    ]


def _gauge(event: dict[str, object]) -> Gauge | None:
    week = _get(_get(event.get("rate_limit_info"), "unifiedWindows"), "seven_day")
    used = _get(week, "utilization")
    ends = _get(week, "resetsAt")
    if not isinstance(used, int | float):
        return None
    return Gauge(float(used), float(ends) if isinstance(ends, int | float) else None)


def read_log(path: Path) -> SessionLog:
    """Read the stream a session left."""
    result: dict[str, object] = {}
    gauges: list[Gauge] = []
    launches: list[Launch] = []
    session_id: str | None = None
    for event in _events(path):
        kind = event.get("type")
        if session_id is None and isinstance(event.get("session_id"), str):
            session_id = str(event["session_id"])
        if kind == "rate_limit_event":
            gauge = _gauge(event)
            if gauge is not None:
                gauges.append(gauge)
        elif kind == "assistant" and not event.get("parent_tool_use_id"):
            for use in _tool_uses(event):
                given = use.get("input")
                if use.get("name") in {"Agent", "Task"} and isinstance(given, dict):
                    asked = cast("dict[str, object]", given)
                    model = asked.get("model")
                    launches.append(
                        Launch(
                            str(asked.get("subagent_type")), None if model is None else str(model)
                        )
                    )
        elif kind == "result":
            result = event
    cost = result.get("total_cost_usd")
    return SessionLog(
        path=path,
        session_id=session_id,
        ended=bool(result),
        final=str(result.get("result", "")).strip(),
        cost=float(cost) if isinstance(cost, int | float) else 0.0,
        gauges=tuple(gauges),
        launches=tuple(launches),
    )


def named_in_tool_calls(path: Path, needles: Sequence[str]) -> list[str]:
    """List the needles a tool call of the session names, its agents' calls included.

    This is how a run is checked for what it must never read: the cases of the corpus, with
    their acceptance tests and their reference implementations.
    """
    found: list[str] = []
    for event in _events(path):
        if event.get("type") != "assistant":
            continue
        for use in _tool_uses(event):
            given = json.dumps(use.get("input", {}))
            found.extend(needle for needle in needles if needle in given and needle not in found)
    return found


def _run(command: list[str], cwd: Path, log: Path, until: Callable[[], bool] | None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as out:
        session = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,  # an open standard input would be read as more prompt
            stdout=out,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,  # its own process group, so that a kill takes all of it
        )
        while session.poll() is None:
            if time.monotonic() - started > toy.SESSION_TIMEOUT or (until is not None and until()):
                toy.kill(session)
                break
            time.sleep(POLL)


def run_chain(  # noqa: PLR0913 (one keyword per way to launch a session)
    project: Path,
    prompt: str,
    log: Path,
    *,
    resume: str | None = None,
    agent: str | None = None,
    until: Callable[[], bool] | None = None,
) -> SessionLog:
    """Run one session of the chain in a project, to its end or until `until` holds.

    `agent` runs the session as that single agent of the chain, with its own definition, where
    a probe wants one role alone. A session still running after the timeout of the end to end
    tests is killed.
    """
    command = toy.claude_command(prompt, resume=resume)
    if agent is not None:
        command += ["--agent", agent]
    _run(command, project, log, until)
    return read_log(log)


def ask(  # noqa: PLR0913 (one keyword per thing a model call is given)
    prompt: str,
    log: Path,
    *,
    system: str,
    model: str,
    cwd: Path,
    tools: Sequence[str] = (),
) -> SessionLog:
    """Ask one model one thing, under its own system prompt, with the tools named and no other.

    No user setting, no server, nothing kept of the session: the answer depends on what is
    given here alone. Runs in the container too, where a tool reads only what is mounted.
    """
    if not toy.in_container():
        raise toy.OutsideContainerError
    command = [
        "claude",
        "--print",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--setting-sources",
        "project,local",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--permission-mode",
        "bypassPermissions",
        "--model",
        model,
        "--system-prompt",
        system,
        "--tools",
        ",".join(tools),
    ]
    _run(command, cwd, log, None)
    return read_log(log)
