"""Shared builders of the evaluation tests: a stream as a session leaves it, a run as it is kept."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from surface_evals.corpus import Case, Diagram
from surface_evals.runner import GATE, RECORD

BLUEPRINT = """\
# Overdue list: blueprint

Revision 1, drawn from `plan.md`.

## The idea in one sentence

A command lists the loans past their due date.

## Acceptance criteria

1. `overdue` prints one line per late loan.
2. The latest comes first.

## Scope and out of scope

In scope: the command. Out of scope: reminders.

## The overdue command

It reads the open loans and prints those past their due date.

## Sensitive zones

Critical zones touched, among those the repository's agent instructions declare: none.

No change: the data schema, the state machines.
"""

PLAN = f"""\
# Plan: overdue list

## Acceptance criteria

1. `overdue` prints one line per late loan.

## Slices

<!-- slice:1 -->
### Slice 1: the command

## Gates

```gates
{GATE}
```
"""


def stream(  # noqa: PLR0913 (what a stream may hold, each by its name)
    path: Path,
    *,
    session: str = "s-1",
    cost: float | None = 0.5,
    final: str = "Done.",
    gauges: Sequence[float] = (),
    agents: Sequence[tuple[str, str | None]] = (),
    reads: Sequence[str] = (),
) -> Path:
    """Write the stream of a session: its gauge readings, its tool calls, its result if it ended."""
    events: list[dict[str, object]] = [{"type": "system", "subtype": "init", "session_id": session}]
    for gauge in gauges:
        windows = {"unifiedWindows": {"seven_day": {"utilization": gauge}}}
        events.append({"type": "rate_limit_event", "rate_limit_info": windows})
    uses: list[dict[str, object]] = []
    for agent, model in agents:
        launched = {"subagent_type": agent, "model": model}
        uses.append({"type": "tool_use", "name": "Agent", "input": launched})
    read_calls: list[dict[str, object]] = [
        {"type": "tool_use", "name": "Read", "input": {"file_path": read}} for read in reads
    ]
    uses.extend(read_calls)
    if uses:
        events.append({"type": "assistant", "message": {"content": uses}})
    if cost is not None:
        events.append(
            {"type": "result", "session_id": session, "total_cost_usd": cost, "result": final}
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    return path


def case(root: Path, **changes: object) -> Case:
    """Make a case of one behavior that touches no critical zone, with the changes named."""
    fields: dict[str, object] = {
        "root": root,
        "shape": "one-behavior",
        "summary": "list the overdue loans",
        "body_sections": (1, 1),
        "diagram": Diagram.NONE,
        "critical_zones": (),
        "critical_files": (),
        "amendment": None,
    }
    return Case(**{**fields, **changes})  # type: ignore[arg-type]


def kept_run(  # noqa: PLR0913 (what a run may have left, each by its name)
    root: Path,
    *,
    journal: Sequence[Mapping[str, object]],
    outcome: str = "conformant",
    stops: Sequence[Mapping[str, object]] = (),
    blueprints: Sequence[str] = (BLUEPRINT,),
    conformity: str | None = None,
    acceptance: Mapping[str, object] | None = None,
    stop_at_hand_over: bool = False,
) -> Path:
    """Write the folder a run leaves: its record, its blueprints, its plan folder."""
    folder = root / "work" / "lending" / "docs" / "plans" / "2026-01-15-overdue"
    folder.mkdir(parents=True)
    (folder / "journal.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in journal), encoding="utf-8"
    )
    (folder / "plan.md").write_text(PLAN, encoding="utf-8")
    (folder / "blueprint.md").write_text(blueprints[-1], encoding="utf-8")
    (folder / "interview.md").write_text("# Interview\n", encoding="utf-8")
    if conformity is not None:
        (folder / "conformity.md").write_text(conformity, encoding="utf-8")
    names: list[str] = []
    for number, text in enumerate(blueprints, start=1):
        names.append(f"blueprint-rev-{number:02d}.md")
        (root / names[-1]).write_text(text, encoding="utf-8")
    record = {
        "v": 1,
        "case": "01-overdue-list",
        "project": "work/lending",
        "plan": "docs/plans/2026-01-15-overdue",
        "stop_at_hand_over": stop_at_hand_over,
        "outcome": outcome,
        "approved_by_sentence": False,
        "stops": list(stops),
        "blueprints": names,
        "acceptance": acceptance,
        # A run that stops at the hand over runs no gate on a code it never asked for.
        "gate": None if stop_at_hand_over else True,
    }
    (root / RECORD).write_text(json.dumps(record), encoding="utf-8")
    (root / "pr-body.md").write_text("## Plans on this branch\n", encoding="utf-8")
    return root
