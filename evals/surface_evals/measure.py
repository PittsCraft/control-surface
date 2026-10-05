"""Does the chain meet its goals: measured from what a run left, by a script alone.

Every measure is read from files: the journal, the plan folder, the streams of the sessions and
the delivered code. A measure that does not apply to a run is None, and stays out of the means:
the proof of conformity of a plan that never got there, the cut kept by a revision that was never
asked for, and everything the execution gives when the run stopped at the hand over.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from surface_evals import blueprint as form
from surface_evals.corpus import Case, Diagram
from surface_evals.runner import GATE, RECORD, stops_at_hand_over
from surface_evals.sessions import SessionLog, named_in_tool_calls, read_log
from surface_status.plan_folder import PlanFolderError, parse_critical_files, parse_gates
from surface_status.plan_folder import parse_slice_markers as parse_slices

# The key phrases of the critical zones the host declares in its `AGENTS.md`.
ZONES = ("fine computation", "loans.jsonl")
# What a session must never read: the clone the container mounts, where the cases are kept
# with their acceptance tests and their reference implementations.
HIDDEN = ("/clone/", "evals/cases")
PLAN_AGENT = "Plan"
# The stops that launch the loop: what their sessions cost is the cost of the execution.
LAUNCHES = frozenset({"approval", "relaunch"})
# What the execution gives, or adds to. A run that stops at the hand over holds none of it,
# whatever its outcome, and each is None for it: a 0 or a False would read as a run that failed
# to conform, and would join the spread of the runs played whole.
EXECUTION = (
    "conformant",
    "acceptance",
    "acceptance_all",
    "gate",
    "usd",
    "approvals",
    "killed",
    "relaunches",
    "reviews",
    "findings",
    "fixes",
    "gate_runs_failed",
    "critical_files",
    "zones_files_listed",
    "zones_consistent",
)

Measures = dict[str, float | bool | str | list[str] | None]


def _number(line: dict[str, object], key: str) -> int:
    value = line.get(key)
    return value if isinstance(value, int) else 0


def cost_of(logs: Sequence[SessionLog]) -> float:
    """Sum the cost of sessions, a resumed one counted once: its stream reports its total."""
    paid: dict[str, float] = {}
    for log in logs:
        key = log.session_id or str(log.path)
        paid[key] = max(paid.get(key, 0.0), log.cost)
    return sum(paid.values())


def _loop(journal: list[dict[str, object]], record: dict[str, object]) -> Measures:
    """Whether the loop converged, and what it took: the passes, the hand back, the approval."""
    by_event: dict[str, list[dict[str, object]]] = {}
    for line in journal:
        by_event.setdefault(str(line.get("event")), []).append(line)
    checks = by_event.get("check-done", [])
    reviews = by_event.get("review-done", [])
    blocked = by_event.get("blocked", [])
    stops = cast("list[dict[str, object]]", record["stops"])
    return {
        "approved_by_sentence": cast("bool | None", record["approved_by_sentence"]),
        "approvals": len(by_event.get("plan-approved", [])),
        "questions": sum(1 for stop in stops if stop["kind"] == "answer"),
        # What the developer had to send back once they read the blueprint: the interview and
        # the blueprint did not carry what they knew.
        "corrections": sum(1 for stop in stops if stop["kind"] == "correction"),
        "killed": sum(1 for stop in stops if not stop["ended"]),
        "relaunches": sum(1 for stop in stops if stop["kind"] == "relaunch"),
        "checks": len(checks),
        "omissions": sum(_number(line, "omissions") for line in checks),
        "planning_passes": sum(1 for line in checks if _number(line, "omissions") > 0),
        "reviews": len(reviews),
        "findings": sum(
            _number(line, key) for line in reviews for key in ("defects", "deviations", "breaks")
        ),
        "fixes": len(by_event.get("fix-done", [])),
        "gate_runs_failed": sum(
            1 for line in by_event.get("gates-run", []) if line.get("result") != "pass"
        ),
        "hand_back": str(blocked[-1].get("why")) if blocked else None,
    }


def _plan(folder: Path, logs: Sequence[SessionLog]) -> Measures:
    """Whether the plan was drafted by the built-in agent, and holds what the chain reads."""
    drafts = [launch for log in logs for launch in log.launches if launch.agent == PLAN_AGENT]
    try:
        text = (folder / "plan.md").read_text(encoding="utf-8")
        minimum: bool | None = bool(parse_slices(text)) and parse_gates(text) == (GATE,)
    except OSError:
        minimum = None
    except PlanFolderError:
        minimum = False
    return {
        "plan_drafts": len(drafts),
        "plan_models": sorted({str(launch.model) for launch in drafts}),
        "plan_minimum": minimum,
    }


def _zones(case: Case, drawn: form.Blueprint | None, folder: Path, *, conformant: bool) -> Measures:
    """Whether the critical zones were named at approval, and their files listed at conformity."""
    zones = "" if drawn is None else drawn.zones.lower()
    # The section opens on the critical zones, or on the statement that the plan touches none.
    opening = zones.split("\n\n", 1)[0]
    named = [phrase for phrase in ZONES if phrase.lower() in zones]
    expected = [phrase.lower() in zones for phrase in case.critical_zones]
    listed: list[str] | None = None
    if conformant:
        try:
            block = parse_critical_files((folder / "conformity.md").read_text(encoding="utf-8"))
            listed = list(block or ())
        except (OSError, PlanFolderError):
            listed = None
    return {
        "zones_named": None if drawn is None or not expected else all(expected),
        "zones_none_said": (
            None if drawn is None or expected else form.NONE_TOUCHED.search(opening) is not None
        ),
        "critical_files": listed,
        "zones_files_listed": (
            None if listed is None else all(path in listed for path in case.critical_files)
        ),
        # A file listed at conformity belongs to a zone the blueprint named at approval.
        "zones_consistent": None if listed is None or drawn is None else not listed or bool(named),
    }


def _form(case: Case, kept: list[form.Blueprint]) -> Measures:
    """Read the form of the blueprint: its frame, the cut of its body, its diagrams."""
    if not kept:
        return {}
    drawn = kept[-1]
    low, high = case.body_sections
    as_expected: bool | None = None
    if case.diagram is Diagram.SOME:
        as_expected = drawn.diagrams > 0
    elif case.diagram is Diagram.NONE:
        as_expected = drawn.diagrams == 0
    titles = [section.title for section in drawn.body]
    return {
        "frame": drawn.framed,
        "numbered_headings": len(drawn.numbered),
        "criteria": drawn.criteria,
        "body_sections": len(titles),
        "body_titles": titles,
        "body_in_range": low <= len(titles) <= high,
        "diagrams": drawn.diagrams,
        "diagram_as_expected": as_expected,
        "closing_line": drawn.closing_line,
        "words": drawn.words,
        "cut_kept": (
            None if len(kept) == 1 else [section.title for section in kept[0].body] == titles
        ),
    }


def measure(root: Path, case: Case) -> Measures:
    """Measure one run from its folder."""
    record = cast("dict[str, object]", json.loads((root / RECORD).read_text(encoding="utf-8")))
    project = root / str(record["project"])
    plan = record["plan"]
    folder = project / str(plan) if plan is not None else project
    journal_file = folder / "journal.jsonl"
    journal = (
        [
            cast("dict[str, object]", json.loads(line))
            for line in journal_file.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if journal_file.is_file()
        else []
    )
    logs = [read_log(path) for path in sorted((root / "logs").glob("*.jsonl"))]
    kept = [
        form.parse((root / name).read_text(encoding="utf-8"))
        for name in cast("list[str]", record["blueprints"])
    ]
    acceptance = cast("dict[str, object] | None", record["acceptance"])
    ran = 0 if acceptance is None else _number(acceptance, "ran")
    failed = 0 if acceptance is None else _number(acceptance, "failed")
    conformant = record["outcome"] == "conformant"
    hidden = {needle for log in logs for needle in named_in_tool_calls(log.path, HIDDEN)}
    stops = cast("list[dict[str, object]]", record["stops"])
    launched = {root / str(stop["log"]) for stop in stops if stop["kind"] in LAUNCHES}
    measures: Measures = {
        "outcome": str(record["outcome"]),
        "handed_over": bool(kept),
        "conformant": conformant,
        "acceptance": (ran - failed) / ran if ran else None,
        "acceptance_all": ran > 0 and failed == 0 if acceptance is not None else None,
        "gate": cast("bool | None", record["gate"]),
        "contaminated": bool(hidden),
        # What planning cost, the developer's sessions included: the one cost a run stopped at
        # the hand over and a run played whole both have.
        "planning_usd": round(cost_of([log for log in logs if log.path not in launched]), 4),
        "usd": round(cost_of(logs), 4),
    }
    measures.update(_loop(journal, record))
    measures.update(_plan(folder, logs))
    measures.update(_zones(case, kept[-1] if kept else None, folder, conformant=conformant))
    measures.update(_form(case, kept))
    if stops_at_hand_over(root):
        for name in EXECUTION:
            measures[name] = None
    return measures
