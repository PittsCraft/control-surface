"""The judge, checked without a human: a document spoiled on purpose must score below its original.

The originals are the documents of the toy project of the end to end tests: its need, its
interview, its blueprint, written out by hand. `evals/judge/spoiled/` holds each of them spoiled
in one known way, with the criterion that way must lower. A pair may bring its own original
where the toy's would not do: a blueprint is padded from a lean one, since padding added to a
page that already repeats itself shows nothing. A judge that scores the spoiled one as
high as the original cannot be trusted on that criterion, and the report says so.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import cast

import toy

from surface_evals import JUDGE
from surface_evals.budget import Ledger
from surface_evals.judge import Dimension, JudgeError, Judgement, judge, load_rubric

SPOILED = JUDGE / "spoiled"
RECORD = "judge-check.json"


@dataclass(frozen=True, slots=True)
class Pair:
    name: str
    what: str
    dimension: str
    criterion: str
    replaces: str  # the document of the originals the spoiled one takes the place of
    original: str | None  # the pair's own original of that document, else the toy's
    spoiled: str  # its text


def originals() -> dict[str, str]:
    return {"need": toy.SPECS, "interview": toy.INTERVIEW, "blueprint": toy.BLUEPRINT}


def load_pairs() -> list[Pair]:
    listed = cast(
        "list[dict[str, str | None]]", json.loads((SPOILED / "pairs.json").read_text("utf-8"))
    )

    def text(name: str | None) -> str | None:
        return None if name is None else (SPOILED / name).read_text(encoding="utf-8")

    return [
        Pair(
            name=str(item["name"]),
            what=str(item["what"]),
            dimension=str(item["dimension"]),
            criterion=str(item["criterion"]),
            replaces=str(item["replaces"]),
            original=text(item["original"]),
            spoiled=str(text(item["with"])),
        )
        for item in listed
    ]


def documents(pair: Pair, *, spoiled: bool) -> dict[str, str]:
    """Give the documents a pair is judged on: its original, or the same with one spoiled."""
    given = originals()
    if pair.original is not None:
        given[pair.replaces] = pair.original
    if spoiled:
        given[pair.replaces] = pair.spoiled
    return given


def check(out: Path, *, model: str, repeats: int, ledger: Ledger) -> Path:
    """Judge each original and each spoiled document, and keep whether the spoiled one fell."""
    system, dimensions = load_rubric()
    by_id = {dimension.id: dimension for dimension in dimensions}
    root = out / "judge-check"
    code = toy.build(toy.State.SPECS, root / f"work-{len(list(root.glob('work-*'))) + 1:02d}")
    refused: list[str] = []

    def judged(dimension: Dimension, documents: dict[str, str], tag: str) -> list[Judgement]:
        found: list[Judgement] = []
        for repeat in range(1, repeats + 1):
            if ledger.exhausted() is not None:
                break
            log = root / "logs" / f"{tag}-{repeat:02d}.jsonl"
            try:
                found += judge(
                    dimension, documents, log, system=system, model=model, ledger=ledger, code=code
                )
            except JudgeError as error:
                refused.append(str(error))
        return found

    # The same originals are judged once per dimension, whatever the number of pairs on them.
    pairs = load_pairs()
    originals_judged: dict[tuple[str, str], list[Judgement]] = {}
    results: list[dict[str, object]] = []
    for pair in pairs:
        given = documents(pair, spoiled=False)
        key = (pair.dimension, given[pair.replaces])
        if key not in originals_judged:
            originals_judged[key] = judged(by_id[pair.dimension], given, f"original-{pair.name}")
        spoiled = judged(
            by_id[pair.dimension], documents(pair, spoiled=True), f"spoiled-{pair.name}"
        )
        before = [item.score for item in originals_judged[key] if item.criterion == pair.criterion]
        after = [item.score for item in spoiled if item.criterion == pair.criterion]
        results.append(
            {
                "name": pair.name,
                "what": pair.what,
                "criterion": f"{pair.dimension}.{pair.criterion}",
                "original": before,
                "spoiled": after,
                "below": bool(before and after) and fmean(after) < fmean(before),
            }
        )
    path = out / RECORD
    kept = {"v": 1, "model": model, "pairs": results, "refused": refused}
    path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
    return path
