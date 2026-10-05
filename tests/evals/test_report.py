"""The report of a campaign, and what moved since the one before (evals/surface_evals/report.py)."""

import json
from pathlib import Path
from typing import cast

from support import kept_run, stream
from test_measure import DRAFTED, JOURNAL, PLANNED, STOPS

from surface_evals import CASES
from surface_evals.judge import IN_PLANNING
from surface_evals.measure import EXECUTION
from surface_evals.report import (
    DIRECTION,
    EM_DASH,
    GOALS,
    Spread,
    chain_version,
    compare,
    render,
    summarize,
    write,
)
from surface_evals.runner import STOPPED


def _summary(cases: dict[str, dict[str, list[float]]]) -> dict[str, object]:
    """Fold values per case into the shape of a summary, the measure named `conformant`."""
    folded = {
        name: {
            "shape": "one-behavior",
            "runs": len(next(iter(values.values()))),
            "outcomes": ["conformant"],
            "measures": {key: Spread.of(found).to_dict() for key, found in values.items()},
            "judge": {},
        }
        for name, values in cases.items()
    }
    return {
        "v": 1,
        "at": "2026-01-15T10:00:00Z",
        "chain": "abc",
        "cases": folded,
        "all": {"runs": 1, "measures": {}, "judge": {}},
        "probes": [],
        "judge_check": None,
        "spent": None,
    }


def test_a_measure_is_kept_as_its_mean_and_its_spread_between_runs() -> None:
    spread = Spread.of([1.0, 0.0, 1.0, 1.0])
    assert (spread.mean, spread.low, spread.high, spread.n) == (0.75, 0.0, 1.0, 4)
    assert Spread.from_dict(spread.to_dict()) == spread


def test_a_measure_moved_only_when_it_lies_outside_the_spread_between_runs() -> None:
    before = _summary({"case": {"acceptance": [0.5, 0.75], "usd": [2.0, 3.0], "questions": [2]}})
    within = _summary({"case": {"acceptance": [0.75, 1.0], "usd": [3.0, 4.0], "questions": [2]}})
    assert compare(within, before) == []
    after = _summary({"case": {"acceptance": [0.25, 0.4], "usd": [1.0, 1.5], "questions": [5]}})
    moves = {move.measure: move.verdict for move in compare(after, before)}
    # Fewer tests accepted is worse, a cheaper run is better, more questions is neither.
    assert moves == {"acceptance": "worse", "usd": "better", "questions": "moved"}


def test_every_goal_with_a_better_way_is_a_measure_the_runs_give() -> None:
    assert set(DIRECTION) & set(GOALS)
    assert DIRECTION["conformant"] == 1
    assert DIRECTION["approved_by_sentence"] == -1
    assert DIRECTION["contaminated"] == -1
    assert "questions" not in DIRECTION


def test_the_version_of_the_chain_names_its_prompts() -> None:
    assert len(chain_version()) == 12
    assert chain_version() == chain_version()


def test_a_campaign_is_summarized_and_reported_from_its_folder(tmp_path: Path) -> None:
    name = min(path.name for path in CASES.iterdir() if (path / "case.json").is_file())
    root = kept_run(
        tmp_path / "runs" / name / "run-01",
        journal=JOURNAL,
        stops=STOPS,
        acceptance={"ran": 4, "failed": 0, "output": ""},
    )
    stream(root / "logs" / "01-need.jsonl", cost=1.25)
    verdict = {
        "dimension": "blueprint",
        "criterion": "decidable",
        "score": 4,
        "reason": "The order of ties is not said.",
        "passage": "the most days late first",
        "grounded": True,
    }
    (root / "judge.json").write_text(
        json.dumps({"v": 1, "model": "opus", "judgements": [verdict], "refused": []}), "utf-8"
    )
    probe = {"name": "seeded-defect", "kind": "reviewer", "what": "a defect", "passed": True}
    kept = tmp_path / "probes" / "seeded-defect" / "run-01"
    kept.mkdir(parents=True)
    (kept / "probe.json").write_text(json.dumps({**probe, "counts": {"defects": 1}}), "utf-8")
    (tmp_path / "ledger.json").write_text(
        json.dumps({"usd": 1.25, "points": 1.0, "sessions": 1}), encoding="utf-8"
    )
    summary = summarize(tmp_path)
    cases = cast("dict[str, dict[str, dict[str, dict[str, float]]]]", summary["cases"])
    assert list(cases) == [name]
    assert cases[name]["measures"]["conformant"] == {"mean": 1.0, "low": 1.0, "high": 1.0, "n": 1}
    assert cases[name]["measures"]["acceptance"]["mean"] == 1.0
    assert cases[name]["judge"]["blueprint.decidable"]["mean"] == 4.0
    assert (root / "measures.json").is_file()
    written, report = write(tmp_path, None)
    assert json.loads(written.read_text(encoding="utf-8"))["chain"] == chain_version()
    text = report.read_text(encoding="utf-8")
    assert "## Does it meet its goals" in text
    assert f"| | {name} | all |" in text
    assert "| `conformant` | 1 | 1 |" in text
    assert "## Faults put there on purpose" in text
    assert "| `seeded-defect` | a defect |" in text
    assert "## Is it good to work with" in text
    assert "| `blueprint.decidable` | 4 | 4 |" in text
    remark = f"- `blueprint.decidable`, 4 in `{name}`: The order of ties is not said."
    assert f'{remark} Passage: "the most days late first"' in text
    assert "1 sessions, 1.25 USD at list price" in text
    assert "What moved" not in text
    # Against itself, nothing moved.
    _, again = write(tmp_path, written)
    assert "Nothing lies outside the spread between runs." in again.read_text(encoding="utf-8")


def _judged(root: Path, scores: dict[str, int]) -> None:
    """Keep the verdicts of a run: one score per criterion, named by dimension and criterion."""
    judgements = [
        {
            "dimension": key.split(".")[0],
            "criterion": key.split(".")[1],
            "score": score,
            "reason": "Said.",
            "passage": "one line per late loan",
            "grounded": True,
        }
        for key, score in scores.items()
    ]
    kept = {"v": 1, "model": "opus", "judgements": judgements, "refused": []}
    (root / "judge.json").write_text(json.dumps(kept), encoding="utf-8")


def _whole(root: Path) -> None:
    """Keep a run played whole: conformant, every hidden test passed, a page that repeats itself."""
    kept_run(
        root,
        journal=JOURNAL,
        stops=STOPS,
        acceptance={"ran": 4, "failed": 0, "output": ""},
        conformity="# Conformity\n",
    )
    stream(root / "logs" / "02-answer.jsonl", session="plan", cost=1.0)
    stream(root / "logs" / "04-approval.jsonl", session="execute", cost=2.0)
    _judged(root, {"blueprint.no-padding": 2, "messages.clear": 2})


def _stopped(root: Path) -> None:
    """Keep a run that stopped at the hand over: a dearer planning, a page that says it once."""
    kept_run(root, journal=DRAFTED, outcome=STOPPED, stops=PLANNED, stop_at_hand_over=True)
    stream(root / "logs" / "02-answer.jsonl", session="plan", cost=1.5)
    _judged(root, {"blueprint.no-padding": 4, f"messages{IN_PLANNING}.clear": 5})


def test_a_run_that_stopped_at_the_hand_over_joins_no_spread_of_the_execution(
    tmp_path: Path,
) -> None:
    name = min(path.name for path in CASES.iterdir() if (path / "case.json").is_file())
    _whole(tmp_path / "runs" / name / "run-01")
    _stopped(tmp_path / "runs" / name / "run-02")
    summary = summarize(tmp_path)
    found = cast("dict[str, dict[str, object]]", summary["cases"])[name]
    assert found["outcomes"] == ["conformant", STOPPED]
    measures = cast("dict[str, dict[str, float]]", found["measures"])
    # Both runs planned, and both count in what planning gives.
    assert measures["questions"]["n"] == 2
    assert measures["planning_usd"] == {"mean": 1.25, "low": 1.0, "high": 1.5, "n": 2}
    # One alone was played whole: the other counts in nothing the execution gives. The list of
    # the critical files is told, never folded.
    assert set(EXECUTION) - set(measures) == {"critical_files"}
    assert {measures[key]["n"] for key in EXECUTION if key in measures} == {1}
    assert measures["conformant"]["mean"] == 1.0
    assert measures["usd"]["mean"] == 3.0
    assert cast("dict[str, object]", summary["all"])["stopped_at_hand_over"] == 1
    text = render(summary)
    assert "1 of these runs played planning alone, on purpose" in text
    assert "| `conformant` | 1 | 1 |" in text


def test_a_campaign_stopped_at_the_hand_over_says_nothing_of_the_execution_against_one_played_whole(
    tmp_path: Path,
) -> None:
    name = min(path.name for path in CASES.iterdir() if (path / "case.json").is_file())
    for run in ("run-01", "run-02"):
        _whole(tmp_path / "before" / "runs" / name / run)
        _stopped(tmp_path / "after" / "runs" / name / run)
    before, after = summarize(tmp_path / "before"), summarize(tmp_path / "after")
    moves = compare(after, before)
    # What both campaigns measured is compared: the page, and what planning cost. Nothing is said
    # of conformity, of the acceptance, of the approvals, of the reviews, of the cost of a run,
    # nor of the messages, which the judge read to the end in one campaign and not in the other.
    assert {(move.scope, move.measure): move.verdict for move in moves} == {
        (name, "blueprint.no-padding"): "better",
        (name, "planning_usd"): "worse",
        ("all", "blueprint.no-padding"): "better",
        ("all", "planning_usd"): "worse",
    }
    text = render(after, moves)
    assert "2 of these runs played planning alone, on purpose" in text
    assert f"dimensions that end in `{IN_PLANNING}`" in text
    assert "| `planning_usd` | 1.5 | 1.5 |" in text
    assert f"| `messages{IN_PLANNING}.clear` | 5 | 5 |" in text
    # No row of the execution, where a 0 would read as a campaign that did not conform.
    for absent in ("conformant", "acceptance", "reviews", "fixes", "usd", "messages.clear"):
        assert f"| `{absent}` |" not in text
    # A campaign played whole says nothing of runs that stopped.
    assert "played planning alone" not in render(before)


def test_the_report_holds_no_em_dash_whatever_a_model_wrote() -> None:
    summary = _summary({"case": {"conformant": [1.0]}})
    summary["probes"] = [
        {
            "name": "p",
            "kind": "checker",
            "what": f"a plan {EM_DASH} spoiled",
            "omissions": 1,
            "passed": True,
        }
    ]
    text = render(summary)
    assert EM_DASH not in text
    assert "a plan ,  spoiled" in text
