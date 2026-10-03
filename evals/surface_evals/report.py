"""The report of a campaign: what the runs of an output folder show, and what moved since.

`summarize` reads every run, every probe and every verdict of the folder, with no session: it
runs anywhere. A measure is kept per case as its mean, its lowest and its highest value over the
runs, since a model does not take the same path twice. `compare` sets two summaries side by
side: a measure moved when the values of one campaign lie wholly outside those of the other, so
that the spread between runs is not read as a change. Nothing fails: the report says what moved,
and in which direction, and the developer decides what to hold.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from statistics import fmean
from typing import cast

from surface_evals import CLONE
from surface_evals.budget import LEDGER
from surface_evals.corpus import load_cases
from surface_evals.judge import VERDICTS
from surface_evals.judge_check import RECORD as JUDGE_CHECK
from surface_evals.measure import Measures, measure
from surface_evals.probes import RECORD as PROBE
from surface_evals.runner import RECORD as RUN

SUMMARY = "summary.json"
REPORT = "report.md"
EM_DASH = chr(0x2014)  # a code point, so this file holds no literal em dash

# Which way is better, for the measures that have one: +1 the higher, -1 the lower. The others
# are told and compared, never called better or worse.
DIRECTION = {
    "handed_over": 1,
    "conformant": 1,
    "acceptance": 1,
    "acceptance_all": 1,
    "gate": 1,
    "contaminated": -1,
    "approved_by_sentence": -1,
    "corrections": -1,
    "killed": -1,
    "relaunches": -1,
    "planning_passes": -1,
    "gate_runs_failed": -1,
    "plan_minimum": 1,
    "zones_named": 1,
    "zones_none_said": 1,
    "zones_files_listed": 1,
    "zones_consistent": 1,
    "frame": 1,
    "numbered_headings": -1,
    "body_in_range": 1,
    "diagram_as_expected": 1,
    "cut_kept": 1,
    "usd": -1,
}
# The measures of the goals table, in the order of the questions the evaluation answers.
GOALS = (
    "handed_over",
    "conformant",
    "acceptance",
    "approved_by_sentence",
    "questions",
    "corrections",
    "planning_passes",
    "reviews",
    "fixes",
    "zones_named",
    "zones_none_said",
    "zones_files_listed",
    "zones_consistent",
    "frame",
    "body_sections",
    "body_in_range",
    "diagrams",
    "diagram_as_expected",
    "cut_kept",
    "plan_minimum",
    "contaminated",
    "usd",
)


@dataclass(frozen=True, slots=True)
class Spread:
    """One measure over the runs of a case: its mean, and how far it goes between runs."""

    mean: float
    low: float
    high: float
    n: int

    @classmethod
    def of(cls, values: Sequence[float]) -> "Spread":
        return cls(round(fmean(values), 4), min(values), max(values), len(values))

    def to_dict(self) -> dict[str, float | int]:
        return {"mean": self.mean, "low": self.low, "high": self.high, "n": self.n}

    @classmethod
    def from_dict(cls, kept: Mapping[str, float]) -> "Spread":
        return cls(float(kept["mean"]), float(kept["low"]), float(kept["high"]), int(kept["n"]))


def chain_version() -> str:
    """Name the version of the chain a campaign ran: a hash of its prompts and of its script."""
    digest = sha256()
    for folder in ("agents", "skills"):
        for path in sorted((CLONE / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                digest.update(path.relative_to(CLONE).as_posix().encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _spreads(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, float | int]]:
    """Fold the numeric measures of several runs: a truth counts 1, what does not apply is left."""
    values: dict[str, list[float]] = {}
    for row in rows:
        for key, value in row.items():
            if isinstance(value, bool | int | float):
                values.setdefault(key, []).append(float(value))
    return {key: Spread.of(found).to_dict() for key, found in sorted(values.items())}


def _verdicts(root: Path) -> dict[str, float | bool]:
    """Fold the verdicts of a run: the mean score of each criterion, and the grounded share."""
    path = root / VERDICTS
    if not path.is_file():
        return {}
    kept = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    judgements = cast("list[dict[str, object]]", kept["judgements"])
    scores: dict[str, list[float]] = {}
    for item in judgements:
        key = f"{item['dimension']}.{item['criterion']}"
        scores.setdefault(key, []).append(float(cast("int", item["score"])))
    folded: dict[str, float | bool] = {key: round(fmean(found), 4) for key, found in scores.items()}
    if judgements:
        folded["grounded"] = round(fmean(float(bool(item["grounded"])) for item in judgements), 4)
    return folded


def summarize(out: Path) -> dict[str, object]:
    """Measure every run of an output folder, and fold them per case."""
    cases: dict[str, object] = {}
    every: list[Measures] = []
    judged: list[dict[str, float | bool]] = []
    for case in load_cases():
        roots = sorted(path.parent for path in (out / "runs" / case.name).glob(f"run-*/{RUN}"))
        if not roots:
            continue
        measures = [measure(root, case) for root in roots]
        verdicts = [folded for root in roots if (folded := _verdicts(root))]
        for root, measured in zip(roots, measures, strict=True):
            (root / "measures.json").write_text(json.dumps(measured, indent=2) + "\n", "utf-8")
        every.extend(measures)
        judged.extend(verdicts)
        cases[case.name] = {
            "shape": case.shape,
            "runs": len(roots),
            "outcomes": [str(found["outcome"]) for found in measures],
            "measures": _spreads(measures),
            "judge": _spreads(verdicts),
        }
    probes = [
        cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((out / "probes").glob(f"*/run-*/{PROBE}"))
    ]
    check = out / JUDGE_CHECK
    ledger = out / LEDGER
    return {
        "v": 1,
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chain": chain_version(),
        "cases": cases,
        "all": {"runs": len(every), "measures": _spreads(every), "judge": _spreads(judged)},
        "probes": probes,
        "judge_check": json.loads(check.read_text(encoding="utf-8")) if check.is_file() else None,
        "spent": json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else None,
    }


@dataclass(frozen=True, slots=True)
class Move:
    """A measure that lies wholly outside what the campaign before it showed."""

    scope: str  # a case, or `all`
    measure: str
    before: Spread
    after: Spread
    verdict: str  # better, worse, or moved when the measure has no better way


def _moves(scope: str, kind: str, after: object, before: object) -> list[Move]:
    new = cast("dict[str, dict[str, float]]", cast("dict[str, object]", after).get(kind, {}))
    old = cast("dict[str, dict[str, float]]", cast("dict[str, object]", before).get(kind, {}))
    moves: list[Move] = []
    for name in sorted(set(new) & set(old)):
        now, then = Spread.from_dict(new[name]), Spread.from_dict(old[name])
        if now.low <= then.high and then.low <= now.high:
            continue  # the two campaigns overlap: within the spread between runs
        way = 1 if kind == "judge" and name != "grounded" else DIRECTION.get(name, 0)
        rose = now.mean > then.mean
        verdict = "moved" if way == 0 else "better" if rose == (way > 0) else "worse"
        moves.append(Move(scope, name, then, now, verdict))
    return moves


def compare(after: Mapping[str, object], before: Mapping[str, object]) -> list[Move]:
    """List what moved between two summaries, case by case, then over all the runs."""
    moves: list[Move] = []
    new = cast("dict[str, object]", after["cases"])
    old = cast("dict[str, object]", before["cases"])
    for name in sorted(set(new) & set(old)):
        for kind in ("measures", "judge"):
            moves.extend(_moves(name, kind, new[name], old[name]))
    for kind in ("measures", "judge"):
        moves.extend(_moves("all", kind, after["all"], before["all"]))
    return moves


def _cell(spread: Mapping[str, float] | None) -> str:
    if spread is None:
        return ""
    if spread["low"] == spread["high"]:
        return f"{spread['mean']:g}"
    return f"{spread['mean']:g} ({spread['low']:g} to {spread['high']:g})"


def _table(summary: Mapping[str, object], kind: str, names: Sequence[str]) -> list[str]:
    cases = cast("dict[str, dict[str, object]]", summary["cases"])
    columns = [*cases, "all"]
    folded = {name: cast("dict[str, dict[str, float]]", cases[name][kind]) for name in cases}
    folded["all"] = cast(
        "dict[str, dict[str, float]]", cast("dict[str, object]", summary["all"])[kind]
    )
    lines = [f"| | {' | '.join(columns)} |", f"|---|{'---|' * len(columns)}"]
    for name in names:
        if any(name in folded[column] for column in columns):
            cells = " | ".join(_cell(folded[column].get(name)) for column in columns)
            lines.append(f"| `{name}` | {cells} |")
    return lines


def render(summary: Mapping[str, object], moves: Sequence[Move] | None = None) -> str:
    """Write the report: the goals, the probes, the judge and its check, the cost, what moved."""
    cases = cast("dict[str, dict[str, object]]", summary["cases"])
    everything = cast("dict[str, object]", summary["all"])
    lines = [
        "# Evaluation of the chain",
        "",
        (
            f"Chain `{summary['chain']}`, measured on {summary['at']}: {everything['runs']} runs"
            f" over {len(cases)} cases. A value is the mean over the runs of a case, with its"
            " lowest and highest when they differ; a truth counts 1. An empty cell does not apply."
        ),
        "",
        "## Does it meet its goals",
        "",
        *_table(summary, "measures", GOALS),
        "",
        "Outcomes: "
        + "; ".join(
            f"`{name}` {', '.join(cast('list[str]', found['outcomes']))}"
            for name, found in cases.items()
        )
        + ".",
    ]
    probes = cast("list[dict[str, object]]", summary["probes"])
    if probes:
        lines += ["", "## Faults put there on purpose", "", "| Probe | What | Found | Passed |"]
        lines.append("|---|---|---|---|")
        for probe in probes:
            found = probe.get("counts") if probe["kind"] == "reviewer" else probe.get("omissions")
            passed = "yes" if probe["passed"] else "no"
            lines.append(
                f"| `{probe['name']}` | {probe['what']} | `{json.dumps(found)}` | {passed} |"
            )
    judged = cast("dict[str, dict[str, float]]", everything["judge"])
    if judged:
        lines += ["", "## Is it good to work with", "", "Scores from 1 to 5, by the judge.", ""]
        lines += _table(summary, "judge", sorted(judged))
    check = cast("dict[str, object] | None", summary["judge_check"])
    if check is not None:
        lines += ["", "## The judge, checked", "", "| Spoiled document | Criterion | Original |"]
        lines[-1] += " Spoiled | Below |"
        lines.append("|---|---|---|---|---|")
        for pair in cast("list[dict[str, object]]", check["pairs"]):
            lines.append(
                f"| {pair['what']} | `{pair['criterion']}` | {pair['original']} |"
                f" {pair['spoiled']} | {'yes' if pair['below'] else 'no'} |"
            )
    spent = cast("dict[str, float] | None", summary["spent"])
    if spent is not None:
        lines += [
            "",
            "## Cost",
            "",
            (
                f"{spent['sessions']} sessions, {spent['usd']:.2f} USD at list price. The weekly"
                f" gauge of the subscription rose by {spent['points']:g} points while they ran,"
                " every other use of the account included."
            ),
        ]
    if moves is not None:
        lines += ["", "## What moved since the campaign before", ""]
        if not moves:
            lines.append("Nothing lies outside the spread between runs.")
        for move in moves:
            lines.append(
                f"- `{move.scope}` `{move.measure}`: {_cell(move.before.to_dict())} then"
                f" {_cell(move.after.to_dict())}, {move.verdict}."
            )
    return "\n".join(lines).replace(EM_DASH, ", ") + "\n"


def write(out: Path, against: Path | None) -> tuple[Path, Path]:
    """Summarize an output folder and write `summary.json` and `report.md` in it."""
    summary = summarize(out)
    moves = None
    if against is not None:
        before = cast("dict[str, object]", json.loads(against.read_text(encoding="utf-8")))
        moves = compare(summary, before)
        summary["against"] = {"chain": before["chain"], "at": before["at"]}
    out.mkdir(parents=True, exist_ok=True)
    (out / SUMMARY).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / REPORT).write_text(render(summary, moves), encoding="utf-8")
    return out / SUMMARY, out / REPORT
