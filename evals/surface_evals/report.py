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
from surface_evals.count import COUNTS, GROUNDED, counts_of
from surface_evals.judge import IN_PLANNING, VERDICTS
from surface_evals.judge_check import RECORD as JUDGE_CHECK
from surface_evals.measure import Measures, measure
from surface_evals.probes import RECORD as PROBE
from surface_evals.runner import RECORD as RUN
from surface_evals.runner import stops_at_hand_over

SUMMARY = "summary.json"
REPORT = "report.md"
EM_DASH = chr(0x2014)  # a code point, so this file holds no literal em dash
PASSAGE_LIMIT = 240  # characters of a passage kept in a report

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
    "pr_draft_at_hand_over": 1,
    "pr_described": 1,
    "pr_refreshed": 1,
    "pr_marked_ready": -1,
    "gh_not_played": -1,
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
    "planning_usd": -1,
    "usd": -1,
}
# What a summary folds per case and over all the runs: the measures of the script, the scores
# of the judge, and its counts of the blueprint. A summary kept before the counts has no `count`.
KINDS = ("measures", "judge", "count")
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
    "pr_draft_at_hand_over",
    "pr_described",
    "pr_refreshed",
    "pr_marked_ready",
    "gh_not_played",
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
    "planning_usd",
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


def _lowest(root: Path, case: str, remarks: dict[str, dict[str, object]]) -> None:
    """Keep, per criterion, the judgement of a run that scores lowest so far, with its reason."""
    path = root / VERDICTS
    if not path.is_file():
        return
    kept = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    for item in cast("list[dict[str, object]]", kept["judgements"]):
        key = f"{item['dimension']}.{item['criterion']}"
        score = cast("int", item["score"])
        if key not in remarks or score < cast("int", remarks[key]["score"]):
            passage = str(item["passage"])
            if len(passage) > PASSAGE_LIMIT:
                passage = passage[:PASSAGE_LIMIT] + " [...]"
            remarks[key] = {
                "case": case,
                "score": score,
                "reason": str(item["reason"]),
                "passage": passage,
                "grounded": bool(item["grounded"]),
            }


def summarize(out: Path) -> dict[str, object]:
    """Measure every run of an output folder, and fold them per case."""
    cases: dict[str, object] = {}
    every: list[Measures] = []
    judged: list[dict[str, float | bool]] = []
    counted: list[dict[str, float]] = []
    remarks: dict[str, dict[str, object]] = {}
    stopped = 0
    for case in load_cases():
        roots = sorted(path.parent for path in (out / "runs" / case.name).glob(f"run-*/{RUN}"))
        if not roots:
            continue
        stopped += sum(1 for root in roots if stops_at_hand_over(root))
        measures = [measure(root, case) for root in roots]
        verdicts = [folded for root in roots if (folded := _verdicts(root))]
        counts = [found for root in roots if (found := counts_of(root))]
        for root, measured in zip(roots, measures, strict=True):
            (root / "measures.json").write_text(json.dumps(measured, indent=2) + "\n", "utf-8")
        every.extend(measures)
        judged.extend(verdicts)
        counted.extend(counts)
        for root in roots:
            _lowest(root, case.name, remarks)
        cases[case.name] = {
            "shape": case.shape,
            "runs": len(roots),
            "outcomes": [str(found["outcome"]) for found in measures],
            "measures": _spreads(measures),
            "judge": _spreads(verdicts),
            "count": _spreads(counts),
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
        "all": {
            "runs": len(every),
            "stopped_at_hand_over": stopped,
            "measures": _spreads(every),
            "judge": _spreads(judged),
            "count": _spreads(counted),
        },
        "remarks": dict(sorted(remarks.items())),
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


def _way(kind: str, name: str) -> int:
    """Say which way is better: a score the higher, a count the lower, a measure as listed."""
    if kind == "judge" and name != "grounded":
        return 1
    if kind == "count":
        return -1 if name in COUNTS else 0
    return DIRECTION.get(name, 0)


def _moves(scope: str, kind: str, after: object, before: object) -> list[Move]:
    new = cast("dict[str, dict[str, float]]", cast("dict[str, object]", after).get(kind, {}))
    old = cast("dict[str, dict[str, float]]", cast("dict[str, object]", before).get(kind, {}))
    moves: list[Move] = []
    for name in sorted(set(new) & set(old)):
        now, then = Spread.from_dict(new[name]), Spread.from_dict(old[name])
        if now.low <= then.high and then.low <= now.high:
            continue  # the two campaigns overlap: within the spread between runs
        way = _way(kind, name)
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
        for kind in KINDS:
            moves.extend(_moves(name, kind, new[name], old[name]))
    for kind in KINDS:
        moves.extend(_moves("all", kind, after["all"], before["all"]))
    return moves


def uncompared(after: Mapping[str, object], before: Mapping[str, object]) -> list[str]:
    """Say what two summaries cannot be compared on: the counts, when one of them holds none.

    A campaign judged before the judge counted has no count. Left unsaid, "nothing moved" would
    read as a count that stayed where it was.
    """
    now, then = (
        bool(cast("dict[str, object]", summary["all"]).get("count")) for summary in (after, before)
    )
    if now == then:
        return []
    without = "the campaign before" if now else "this campaign"
    return [f"Not compared: the counts of the blueprint, which {without} does not hold."]


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


def _probes(summary: Mapping[str, object]) -> list[str]:
    probes = cast("list[dict[str, object]]", summary["probes"])
    if not probes:
        return []
    lines = ["", "## Faults put there on purpose", "", "| Probe | What | Found | Passed |"]
    lines.append("|---|---|---|---|")
    for probe in probes:
        found = probe.get("counts") if probe["kind"] == "reviewer" else probe.get("omissions")
        passed = "yes" if probe["passed"] else "no"
        lines.append(f"| `{probe['name']}` | {probe['what']} | `{json.dumps(found)}` | {passed} |")
    return lines


def _judged(summary: Mapping[str, object]) -> list[str]:
    judged = cast("dict[str, object]", summary["all"])["judge"]
    if not judged:
        return []
    names = sorted(cast("dict[str, object]", judged))
    lines = ["", "## Is it good to work with", "", "Scores from 1 to 5, by the judge.", ""]
    lines += _table(summary, "judge", names)
    lines += [
        "",
        "The lowest score of each criterion, with the judge's reason and its passage:",
        "",
    ]
    for name, remark in cast("dict[str, dict[str, object]]", summary.get("remarks", {})).items():
        rests = "" if remark["grounded"] else " (in no document the judge was given)"
        lines.append(
            f"- `{name}`, {remark['score']} in `{remark['case']}`: {remark['reason']}"
            f" Passage{rests}: {json.dumps(remark['passage'])}"
        )
    return lines


def _counted(summary: Mapping[str, object]) -> list[str]:
    counted = cast("dict[str, object]", summary["all"]).get("count")
    if not counted:
        return []
    return [
        "",
        "## What the developer would skip on the blueprint",
        "",
        (
            "Counted by the judge on the blueprint alone, lower being better: the facts the page"
            " says more than once in prose, the details of implementation that are not the"
            " developer's to decide, and the share of its words they could skip, in percent,"
            f" which is an estimate. `{GROUNDED}` is the share of the passages these counts rest"
            " on that stand on the page. The facts, the details and their passages are in the"
            " `count.json` of each run."
        ),
        "",
        *_table(summary, "count", (*COUNTS, GROUNDED)),
    ]


def _checked(summary: Mapping[str, object]) -> list[str]:
    check = cast("dict[str, object] | None", summary["judge_check"])
    if check is None:
        return []
    lines = ["", "## The judge, checked", ""]
    lines.append("| Spoiled document | Criterion | Original | Spoiled | Below |")
    lines.append("|---|---|---|---|---|")
    lines += [
        f"| {pair['what']} | `{pair['criterion']}` | {pair['original']} |"
        f" {pair['spoiled']} | {'yes' if pair['below'] else 'no'} |"
        for pair in cast("list[dict[str, object]]", check["pairs"])
    ]
    # A check kept before the judge counted has no counts.
    counts = cast("list[dict[str, object]]", check.get("counts", []))
    if counts:
        lines += ["", "| Spoiled document | Count | Original | Spoiled | Above |"]
        lines.append("|---|---|---|---|---|")
        lines += [
            f"| {pair['what']} | `{pair['count']}` | {pair['original']} |"
            f" {pair['spoiled']} | {'yes' if pair['above'] else 'no'} |"
            for pair in counts
        ]
    return lines


def _spent(summary: Mapping[str, object]) -> list[str]:
    spent = cast("dict[str, float] | None", summary["spent"])
    if spent is None:
        return []
    return [
        "",
        "## Cost",
        "",
        (
            f"{spent['sessions']} sessions, {spent['usd']:.2f} USD at list price. The weekly"
            f" gauge of the subscription rose by {spent['points']:g} points while they ran,"
            " every other use of the account included."
        ),
    ]


def _moved(moves: Sequence[Move] | None, left_out: Sequence[str]) -> list[str]:
    if moves is None:
        return []
    lines = ["", "## What moved since the campaign before", ""]
    if not moves:
        lines.append("Nothing lies outside the spread between runs.")
    lines += [
        f"- `{move.scope}` `{move.measure}`: {_cell(move.before.to_dict())} then"
        f" {_cell(move.after.to_dict())}, {move.verdict}."
        for move in moves
    ]
    for line in left_out:
        lines += ["", line]
    return lines


def _stopped(everything: Mapping[str, object]) -> list[str]:
    """Say how many runs played planning alone, so that no empty cell reads as a failure."""
    stopped = cast("int", everything.get("stopped_at_hand_over", 0))  # not in an older summary
    if not stopped:
        return []
    return [
        "",
        (
            f"{stopped} of these runs played planning alone, on purpose: they went no further"
            " than the hand over, and nothing was approved or built in them. No measure of the"
            " execution counts them, here or against another campaign, and what the judge says"
            f" of their stops is kept apart, under the dimensions that end in `{IN_PLANNING}`."
        ),
    ]


def render(
    summary: Mapping[str, object],
    moves: Sequence[Move] | None = None,
    left_out: Sequence[str] = (),
) -> str:
    """Write the report: the goals, the probes, the judge and its check, the cost, what moved.

    `left_out` is what the two campaigns could not be compared on, told under what moved.
    """
    cases = cast("dict[str, dict[str, object]]", summary["cases"])
    everything = cast("dict[str, object]", summary["all"])
    outcomes = "; ".join(
        f"`{name}` {', '.join(cast('list[str]', found['outcomes']))}"
        for name, found in cases.items()
    )
    lines = [
        "# Evaluation of the chain",
        "",
        (
            f"Chain `{summary['chain']}`, measured on {summary['at']}: {everything['runs']} runs"
            f" over {len(cases)} cases. A value is the mean over the runs of a case, with its"
            " lowest and highest when they differ; a truth counts 1. An empty cell does not apply."
        ),
        *_stopped(everything),
        "",
        "## Does it meet its goals",
        "",
        *_table(summary, "measures", GOALS),
        "",
        f"Outcomes: {outcomes}.",
        *_probes(summary),
        *_judged(summary),
        *_counted(summary),
        *_checked(summary),
        *_spent(summary),
        *_moved(moves, left_out),
    ]
    return "\n".join(lines).replace(EM_DASH, ", ") + "\n"


def write(out: Path, against: Path | None) -> tuple[Path, Path]:
    """Summarize an output folder and write `summary.json` and `report.md` in it."""
    summary = summarize(out)
    moves = None
    left_out: list[str] = []
    if against is not None:
        before = cast("dict[str, object]", json.loads(against.read_text(encoding="utf-8")))
        moves = compare(summary, before)
        left_out = uncompared(summary, before)
        summary["against"] = {"chain": before["chain"], "at": before["at"]}
    out.mkdir(parents=True, exist_ok=True)
    (out / SUMMARY).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / REPORT).write_text(render(summary, moves, left_out), encoding="utf-8")
    return out / SUMMARY, out / REPORT
