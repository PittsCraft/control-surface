"""The evaluations from the command line: run the corpus, the probes and the judge, then report.

    evals/run.py corpus [--case NAME]... [--runs N] [--jobs N] [--stop-at-hand-over]
    evals/run.py probes [--only NAME]... [--runs N]
    evals/run.py judge [--repeats N] [--again]
    evals/run.py judge-check [--repeats N]
    evals/run.py report [--against SUMMARY] [--keep]

Everything but `report` starts real sessions, which are billed and bypass permissions: those
commands run in the container of the end to end tests, through `scripts/gate.sh evals`. `--out`
names the folder a campaign is kept in, runs, probes, verdicts and ledger: `report` reads it and
starts no session, so it runs anywhere.
"""

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from surface_evals import REPORTS, developer, judge, judge_check, probes, report
from surface_evals.budget import Ledger
from surface_evals.corpus import load_cases
from surface_evals.runner import RECORD, Run


def _say(text: str) -> None:
    sys.stdout.write(f"{text}\n")
    sys.stdout.flush()


def _ledger(args: argparse.Namespace) -> Ledger:
    return Ledger.load(args.out, max_usd=args.max_usd, max_points=args.max_week_points)


def _play(run: Run) -> str:
    if run.plan() and run.outcome != "budget":
        run.execute()
    run.close()
    tests = run.acceptance
    passed = "no acceptance test ran" if tests is None else f"{tests.passed}/{tests.ran} accepted"
    return f"{run.case.name} {run.root.name}: {run.outcome}, {passed}"


def _corpus(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    runs: list[Run] = []
    # The folders are taken here, one after the other, so that two runs never share a number.
    for case in load_cases(args.case):
        folder = args.out / "runs" / case.name
        taken = [int(path.name.removeprefix("run-")) for path in folder.glob("run-[0-9][0-9]")]
        for number in range(max(taken, default=0) + 1, max(taken, default=0) + 1 + args.runs):
            root = folder / f"run-{number:02d}"
            root.mkdir(parents=True)
            runs.append(
                Run(
                    case=case,
                    root=root,
                    ledger=ledger,
                    developer_model=args.developer_model,
                    stop_at_hand_over=args.stop_at_hand_over,
                )
            )
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for line in pool.map(_play, runs):
            _say(line)
    stopped = ledger.exhausted()
    if stopped is not None:
        _say(f"stopped: {stopped}")
    return 0


def _probes(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    wanted = set(args.only)
    for _ in range(args.runs):
        for probe in (*probes.CHECKER_PROBES, *probes.REVIEWER_PROBES):
            if wanted and probe.name not in wanted:
                continue
            stopped = ledger.exhausted()
            if stopped is not None:
                _say(f"stopped: {stopped}")
                return 0
            if isinstance(probe, probes.CheckerProbe):
                kept = probes.run_checker_probe(probe, args.out, ledger)
            else:
                kept = probes.run_reviewer_probe(probe, args.out, ledger)
            found = json.loads(kept.read_text(encoding="utf-8"))
            _say(f"{probe.name}: {'passed' if found['passed'] else 'not passed'}")
    return 0


def _judge(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    for case in load_cases():
        for record in sorted((args.out / "runs" / case.name).glob(f"run-*/{RECORD}")):
            root = record.parent
            if (root / judge.VERDICTS).is_file() and not args.again:
                continue
            stopped = ledger.exhausted()
            if stopped is not None:
                _say(f"stopped: {stopped}")
                return 0
            judge.judge_run(root, case, model=args.model, repeats=args.repeats, ledger=ledger)
            _say(f"{case.name} {root.name}: judged")
    return 0


def _judge_check(args: argparse.Namespace) -> int:
    kept = judge_check.check(args.out, model=args.model, repeats=args.repeats, ledger=_ledger(args))
    for pair in json.loads(kept.read_text(encoding="utf-8"))["pairs"]:
        fell = "below its original" if pair["below"] else "NOT below its original"
        _say(f"{pair['name']}: {pair['spoiled']} against {pair['original']}, {fell}")
    return 0


def _report(args: argparse.Namespace) -> int:
    summary, written = report.write(args.out, args.against)
    _say(str(written))
    if args.keep:
        chain = json.loads(summary.read_text(encoding="utf-8"))["chain"]
        kept = REPORTS / f"{datetime.now(UTC).date().isoformat()}-{chain}"
        kept.mkdir(parents=True, exist_ok=True)
        for path in (summary, written):
            shutil.copyfile(path, kept / path.name)
        _say(f"kept in {kept}")
    return 0


def _sessions(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-usd", type=float, help="stop once this much is spent, at list price")
    parser.add_argument(
        "--max-week-points",
        type=float,
        help="stop once the weekly gauge of the subscription rose by this many points",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluations of the chain, on real sessions.")
    parser.add_argument("--out", type=Path, default=Path(".evals"), help="the campaign's folder")
    commands = parser.add_subparsers(dest="command", required=True)

    corpus = commands.add_parser("corpus", help="run the cases, from the need to the code")
    corpus.add_argument("--case", action="append", default=[], help="a case, else all of them")
    corpus.add_argument("--runs", type=int, default=1, help="runs per case")
    corpus.add_argument("--jobs", type=int, default=1, help="runs played at the same time")
    corpus.add_argument("--developer-model", default=developer.MODEL)
    corpus.add_argument(
        "--stop-at-hand-over",
        action="store_true",
        help="play planning alone: stop once the blueprint is handed over and read",
    )
    corpus.set_defaults(play=_corpus)

    seeded = commands.add_parser("probes", help="faults put there on purpose, on the toy")
    seeded.add_argument("--only", action="append", default=[], help="a probe, else all of them")
    seeded.add_argument("--runs", type=int, default=1)
    seeded.set_defaults(play=_probes)

    judged = commands.add_parser("judge", help="judge the runs against the rubric")
    judged.add_argument("--repeats", type=int, default=1)
    judged.add_argument("--model", default=judge.MODEL)
    judged.add_argument("--again", action="store_true", help="judge again the runs already judged")
    judged.set_defaults(play=_judge)

    checked = commands.add_parser("judge-check", help="check the judge on spoiled documents")
    checked.add_argument("--repeats", type=int, default=2)
    checked.add_argument("--model", default=judge.MODEL)
    checked.set_defaults(play=_judge_check)

    told = commands.add_parser("report", help="measure and report, with no session")
    told.add_argument("--against", type=Path, help="the summary.json of an earlier campaign")
    told.add_argument("--keep", action="store_true", help="copy the report under evals/reports/")
    told.set_defaults(play=_report)

    for sub in (corpus, seeded, judged, checked):
        _sessions(sub)
    args = parser.parse_args(argv)
    args.out = args.out.resolve()
    return int(args.play(args))
