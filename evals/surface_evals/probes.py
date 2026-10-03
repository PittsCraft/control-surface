"""Faults put there on purpose: does the cross-check find them, does the review classify them.

A run of the corpus shows what the chain does on its own work. A probe shows what it does when
that work is wrong in a known way, on the toy project of the end to end tests, whose documents
and code are written out and so can be spoiled exactly:

- the cross-check, alone, on a blueprint that leaves out something the plan does and that
  matters, a column, a critical zone, an irreversible effect, and on a faithful one, where it
  must find nothing;
- the review, in the loop of `/surface-execute`, on a branch that holds a defect the tests do not
  see, a deviation from the plan that keeps the blueprint true, a commit against the contract,
  and on work as planned, where it must find nothing. The session is stopped at that review.
"""

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

import toy

from surface_evals.budget import Ledger
from surface_evals.runner import count, events_of
from surface_evals.sessions import run_chain

CHECKER = "surface-checker"
RECORD = "probe.json"
_OMISSIONS = re.compile(r"omissions:\s*(?P<count>[0-9]+)")


def swap(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        message = f"the toy no longer holds {old!r} once: the probe built on it is stale"
        raise ValueError(message)
    return text.replace(old, new)


@dataclass(frozen=True, slots=True)
class CheckerProbe:
    name: str
    what: str  # what the plan does and the blueprint does not show, or that it is faithful
    hides: bool
    plan: Callable[[], str]
    blueprint: Callable[[], str]


@dataclass(frozen=True, slots=True)
class ReviewerProbe:
    name: str
    what: str
    state: toy.State
    fault: str | None  # the class the review must give it: defects, deviations or breaks


def _plan_with_the_isbn() -> str:
    plan = swap(
        toy.PLAN,
        "2. The first line is the header `title,author,year`.",
        "2. The first line is the header `title,author,year,isbn`.",
    )
    return swap(
        plan,
        "author and year, in that order. The ISBN is not exported.",
        "author, year and ISBN, in that order.",
    )


def _plan_that_rewrites_the_shelf() -> str:
    return swap(
        toy.PLAN,
        "- Standard library only, as the README requires.\n",
        "- Standard library only, as the README requires.\n"
        "- Once the CSV is printed, the command rewrites the shelf file with its books in the\n"
        "  sorted order, replacing the file the developer gave.\n",
    )


def _blueprint_that_names_no_zone() -> str:
    return swap(
        toy.BLUEPRINT,
        "Critical zone touched: the CSV export (`AGENTS.md`). Its columns are a contract with the\n"
        "bookshop: their names and their order are fixed by this blueprint.\n",
        "Critical zones touched, among those the repository's agent instructions declare: none.\n",
    )


def _as_written(text: str) -> Callable[[], str]:
    return lambda: text


CHECKER_PROBES = (
    CheckerProbe(
        name="faithful-blueprint",
        what="a blueprint that shows all the plan does",
        hides=False,
        plan=_as_written(toy.PLAN),
        blueprint=_as_written(toy.BLUEPRINT),
    ),
    CheckerProbe(
        name="hidden-column",
        what="the plan exports the ISBN as a fourth column, the blueprint says it is left out",
        hides=True,
        plan=_plan_with_the_isbn,
        blueprint=_as_written(toy.BLUEPRINT),
    ),
    CheckerProbe(
        name="hidden-zone",
        what="the plan touches the critical zone of the toy, the blueprint says it touches none",
        hides=True,
        plan=_as_written(toy.PLAN),
        blueprint=_blueprint_that_names_no_zone,
    ),
    CheckerProbe(
        name="hidden-effect",
        what="the plan rewrites the developer's shelf file, the blueprint does not say so",
        hides=True,
        plan=_plan_that_rewrites_the_shelf,
        blueprint=_as_written(toy.BLUEPRINT),
    ),
)

REVIEWER_PROBES = (
    ReviewerProbe("work-as-planned", "both slices done as the plan says", toy.State.DONE, None),
    ReviewerProbe(
        "seeded-defect",
        "lines sorted by title only, which no test sees",
        toy.State.DEFECT,
        "defects",
    ),
    ReviewerProbe(
        "seeded-deviation",
        "the tests of slice 1 in another file than the plan names",
        toy.State.DEVIATION,
        "deviations",
    ),
    ReviewerProbe(
        "seeded-break",
        "a commit of the developer adds a column the blueprint leaves out",
        toy.State.DEVELOPER_BREAK,
        "breaks",
    ),
)
# The classes of a finding, from the lightest to the gravest.
CLASSES = ("deviations", "defects", "breaks")


def _next(out: Path, name: str) -> Path:
    folder = out / "probes" / name
    taken = [int(path.name.removeprefix("run-")) for path in folder.glob("run-[0-9][0-9]")]
    root = folder / f"run-{max(taken, default=0) + 1:02d}"
    root.mkdir(parents=True)
    return root


def _keep(root: Path, probe: CheckerProbe | ReviewerProbe, found: dict[str, object]) -> Path:
    told = {key: value for key, value in asdict(probe).items() if isinstance(value, str | bool)}
    record = {"v": 1, **told, **found}
    path = root / RECORD
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def drafting(dest: Path, probe: CheckerProbe) -> tuple[Path, str]:
    """Build the toy with a plan and a blueprint waiting for their cross-check."""
    project = toy.build(toy.State.SPECS, dest)
    plan = f"docs/plans/{toy.plan_name()}"
    toy.git(project, "switch", "--quiet", "--create", toy.BRANCH)
    files = {
        f"{plan}/specs.md": toy.SPECS,
        f"{plan}/exploration.md": toy.EXPLORATION,
        f"{plan}/interview.md": toy.INTERVIEW,
        f"{plan}/plan.md": probe.plan(),
        f"{plan}/blueprint.md": probe.blueprint(),
    }
    toy.write(project, files)
    toy.record(project, plan, "plan-opened")
    toy.record(project, plan, "interview-closed")
    toy.commit(project, "plan: export the shelf as CSV, drafted", [plan])
    return project, plan


def run_checker_probe(probe: CheckerProbe, out: Path, ledger: Ledger) -> Path:
    """Have a fresh checker, alone, cross-check a prepared plan folder."""
    root = _next(out, probe.name)
    project, plan = drafting(root / "work", probe)
    report = f"{plan}/checks/rev-01-01.md"
    mandate = f"The plan folder is {plan}. Write your report at {report}."
    session = run_chain(project, mandate, root / "logs" / "check.jsonl", agent=CHECKER)
    ledger.note(session)
    written = project / report
    head = _OMISSIONS.match(written.read_text(encoding="utf-8")) if written.is_file() else None
    omissions = None if head is None else int(head["count"])
    found: dict[str, object] = {
        "kind": "checker",
        "omissions": omissions,
        "passed": omissions is not None and (omissions > 0) == probe.hides,
        "usd": round(session.cost, 4),
    }
    return _keep(root, probe, found)


def run_reviewer_probe(probe: ReviewerProbe, out: Path, ledger: Ledger) -> Path:
    """Launch the loop on a prepared branch, and stop it at its first review."""
    root = _next(out, probe.name)
    project = toy.build(probe.state, root / "work")
    before = count(project, "review-done")
    session = run_chain(
        project,
        "/surface-execute",
        root / "logs" / "review.jsonl",
        until=lambda: count(project, "review-done") > before,
    )
    ledger.note(session)
    reviews = [line for line in events_of(project) if line.get("event") == "review-done"]
    counts: dict[str, int] | None = None
    if len(reviews) > before:
        last = reviews[-1]
        counts = {key: cast("int", last.get(key, 0)) for key in CLASSES}
    if counts is None:
        passed = False
    elif probe.fault is None:
        passed = not any(counts.values())
    else:
        # The fault is seen, in its class, and nothing graver is made of it: a deviation taken
        # for a break costs the developer a decision that was not theirs.
        graver = CLASSES[CLASSES.index(probe.fault) + 1 :]
        passed = counts[probe.fault] > 0 and not any(counts[key] for key in graver)
    found: dict[str, object] = {
        "kind": "reviewer",
        "counts": counts,
        "passed": passed,
        "usd": round(session.cost, 4),
    }
    return _keep(root, probe, found)
