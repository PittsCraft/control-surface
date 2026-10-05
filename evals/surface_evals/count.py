"""What a developer would skip on a blueprint: counted by a model, beside the scores of the judge.

A score from 1 to 5 is too coarse to follow a change of the blueprint: the same score went to
pages that a reader who counts tells apart at once. So the judge also counts, in a call of its
own that leaves the criteria of the rubric as they are asked, on the blueprint alone and by the
method `evals/judge/count.md` writes down: the facts the page states more than once, the details
of implementation that are not the developer's to decide, and the share of the page to skip.
Each fact comes with the passages that state it, each detail with the passage that holds it.

The script holds what a script can. An answer that is not the form asked for is refused. A
passage that is not on the page is marked as not grounded, and one that only a diagram holds is
a statement in a diagram, whatever place it was given. And the totals are counted here, from the
lists, never taken from the model: a total cannot disagree with what it rests on.
"""

import json
import re
import tempfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import cast

from surface_evals import JUDGE
from surface_evals.budget import Ledger
from surface_evals.corpus import Case
from surface_evals.judge import MISSING, JudgeError, documents_of, flat
from surface_evals.sessions import ask

INSTRUCTIONS = JUDGE / "count.md"
COUNTED = "count.json"
# Where a statement stands on the page: the frame, the body between, a diagram wherever it is.
PLACES = ("idea", "criteria", "scope", "body", "diagram", "sensitive-zones", "closing-line")
DIAGRAM = "diagram"
# The measures a count gives. Each is something to skip: the lower, the better.
REPEATED, DETAILS, SKIPPABLE = "repeated_in_prose", "implementation_details", "skippable_percent"
COUNTS = (REPEATED, DETAILS, SKIPPABLE)
GROUNDED = "count_grounded"  # the share of the passages the counts rest on that are on the page
# The criterion of the rubric the count stands beside: its spoiled documents check the count too.
BESIDE = ("blueprint", "no-padding")
TWICE = 2  # a fact is repeated from its second statement
WHOLE = 100  # the share to skip is a percentage

_FENCE = re.compile(r"```(?P<tag>\S*)")


@dataclass(frozen=True, slots=True)
class Statement:
    place: str
    passage: str
    grounded: bool  # the passage stands, word for word, on the page


@dataclass(frozen=True, slots=True)
class Fact:
    fact: str
    statements: tuple[Statement, ...]

    @property
    def in_prose(self) -> bool:
        """Whether prose alone says it twice: a diagram may draw what the prose says."""
        return sum(1 for stated in self.statements if stated.place != DIAGRAM) >= TWICE


@dataclass(frozen=True, slots=True)
class Detail:
    detail: str
    passage: str
    grounded: bool


@dataclass(frozen=True, slots=True)
class Count:
    facts: tuple[Fact, ...]
    details: tuple[Detail, ...]
    skippable_percent: int  # the reader's estimate, where the two other measures are counted
    would_skip: str

    @property
    def numbers(self) -> dict[str, int]:
        """The measures of the page: two counted from the lists, and the share as estimated."""
        return {
            REPEATED: sum(1 for fact in self.facts if fact.in_prose),
            DETAILS: len(self.details),
            SKIPPABLE: self.skippable_percent,
        }

    def kept(self) -> dict[str, object]:
        """Give what is kept of a count: its measures, then the lists and their passages."""
        rests = [stated.grounded for fact in self.facts for stated in fact.statements]
        rests += [detail.grounded for detail in self.details]
        return {
            **self.numbers,
            "would_skip": self.would_skip,
            "passages": len(rests),
            "passages_grounded": sum(rests),
            "facts": [
                {
                    "fact": fact.fact,
                    "in_prose": fact.in_prose,
                    "statements": [asdict(stated) for stated in fact.statements],
                }
                for fact in self.facts
            ],
            "details": [asdict(detail) for detail in self.details],
        }


def load(path: Path = INSTRUCTIONS) -> tuple[str, str]:
    """Read the method: who counts and what a blueprint is, then what is counted."""
    head, _, asked = path.read_text(encoding="utf-8").partition("\n## ")
    if not asked.strip():
        message = f"count: {path.name} has no heading under which it says what to count"
        raise JudgeError(message)
    return head.strip(), f"## {asked.strip()}"


def prompt(asked: str, page: str) -> str:
    """Write what the reader is asked: what to count, the page, the form."""
    passage = '"passage": "<copied word for word from the page>"'
    stated = f'{{"place": "<one of the places>", {passage}}}'
    form = (
        '{"repeated_facts": [{"fact": "<a few words>", "statements": '
        f"[{stated}, {stated}]}}],"
        f' "implementation_details": [{{"detail": "<a few words>", {passage}}}],'
        ' "skippable_percent": <a whole number from 0 to 100>,'
        ' "would_skip": "<one sentence, or nothing>"}'
    )
    return (
        f'{asked}\n\n## The page\n\n<document name="blueprint">\n{page.strip()}\n</document>\n\n'
        "## Your answer\n\nOne JSON object and nothing else, in this form: each repeated fact"
        " with two statements at least, a list left empty when there is nothing to put in it,"
        f" and no total, since they are counted from your lists.\n\n{form}\n"
    )


def _items(holder: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    """Read a list of objects of the answer, refusing anything else under that key."""
    found = holder.get(key)
    items = cast("list[object]", found) if isinstance(found, list) else None
    if items is None or not all(isinstance(item, dict) for item in items):
        message = f"count: `{key}` is not a list of objects"
        raise JudgeError(message)
    return cast("list[Mapping[str, object]]", items)


def _said(holder: Mapping[str, object], key: str) -> str:
    """Read a text of the answer, its spaces made one, empty when it is not a text."""
    value = holder.get(key)
    return flat(value) if isinstance(value, str) else ""


@dataclass(frozen=True, slots=True)
class _Page:
    """A page as passages are looked up on it: its spaces made one, its diagrams told apart."""

    text: str  # the whole page
    prose: str  # the page without its diagrams
    drawn: str  # what its diagrams hold


def _read(page: str) -> _Page:
    prose: list[str] = []
    drawn: list[str] = []
    tag: str | None = None  # of the fence a line stands in, None outside any
    for line in page.splitlines():
        fence = _FENCE.fullmatch(line.strip())
        if fence is not None:
            tag = fence["tag"] if tag is None else None
        elif tag == "mermaid":
            drawn.append(line)
        else:
            prose.append(line)
    return _Page(flat(page), flat("\n".join(prose)), flat("\n".join(drawn)))


def _fact(item: Mapping[str, object], page: _Page) -> Fact:
    name = _said(item, "fact")
    given = _items(item, "statements")
    if not name or len(given) < TWICE:
        message = f"count: a repeated fact has a name and two statements at least, not {item!r}"
        raise JudgeError(message)
    seen: Counter[str] = Counter()
    statements: list[Statement] = []
    for stated in given:
        place = _said(stated, "place").lower().replace(" ", "-")
        if place not in PLACES:
            message = f"count: {name!r} is stated in {stated.get('place')!r}, not one of {PLACES}"
            raise JudgeError(message)
        passage = _said(stated, "passage")
        seen[passage] += 1
        # A passage given twice for one fact is two statements only where the page holds it twice.
        grounded = bool(passage) and page.text.count(passage) >= seen[passage]
        # Where a passage stands is read from the page: one that only a diagram holds is a
        # statement in a diagram, whatever place it was given, and never a repeat in prose.
        if grounded and passage in page.drawn and passage not in page.prose:
            place = DIAGRAM
        statements.append(Statement(place, passage, grounded))
    return Fact(name, tuple(statements))


def _detail(item: Mapping[str, object], text: str) -> Detail:
    name = _said(item, "detail")
    if not name:
        message = f"count: a detail of implementation has a name, not {item!r}"
        raise JudgeError(message)
    passage = _said(item, "passage")
    return Detail(name, passage, bool(passage) and passage in text)


def _share(holder: Mapping[str, object]) -> int:
    share = holder.get("skippable_percent")
    if isinstance(share, str) and share.strip().removesuffix("%").strip().isdecimal():
        share = int(share.strip().removesuffix("%"))  # a number written as a text is the number
    if type(share) is not int or not 0 <= share <= WHOLE:
        message = f"count: the share to skip is {share!r}, not a whole number from 0 to {WHOLE}"
        raise JudgeError(message)
    return share


def parse(answer: str, page: str) -> Count:
    """Read the reader's answer, refusing one that is not the lists and the share asked for."""
    start, end = answer.find("{"), answer.rfind("}")
    try:
        given = cast("Mapping[str, object]", json.loads(answer[start : end + 1]))
    except ValueError as error:
        message = f"count: the answer is not the JSON object asked for: {error}"
        raise JudgeError(message) from error
    read = _read(page)
    return Count(
        facts=tuple(_fact(item, read) for item in _items(given, "repeated_facts")),
        details=tuple(_detail(item, read.text) for item in _items(given, "implementation_details")),
        skippable_percent=_share(given),
        would_skip=_said(given, "would_skip"),
    )


def count(page: str, log: Path, *, model: str, ledger: Ledger) -> Count:
    """Have a page counted, in a folder that holds nothing: the reader is given the page alone."""
    system, asked = load()
    with tempfile.TemporaryDirectory() as scratch:
        session = ask(prompt(asked, page), log, system=system, model=model, cwd=Path(scratch))
    ledger.note(session)
    return parse(session.final, page)


def count_run(root: Path, case: Case, *, model: str, repeats: int, ledger: Ledger) -> Path:
    """Count the blueprint of a run, `repeats` times, and keep the counts in its folder.

    A run that handed no blueprint over keeps no count: a page that is not there has nothing
    to skip, and a zero would read as the best of pages.
    """
    page = documents_of(root, case)["blueprint"]
    counts: list[dict[str, object]] = []
    refused: list[str] = []
    for repeat in range(1, repeats + 1):
        if page == MISSING or ledger.exhausted() is not None:
            break
        log = root / "logs-judge" / f"count-{repeat:02d}.jsonl"
        try:
            found = count(page, log, model=model, ledger=ledger)
        except JudgeError as error:
            refused.append(str(error))
            continue
        counts.append({"repeat": repeat, **found.kept()})
    kept = {"v": 1, "model": model, "counts": counts, "refused": refused}
    path = root / COUNTED
    path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
    return path


def counts_of(root: Path) -> dict[str, float]:
    """Fold the counts of a run: the mean of each measure, and the share of grounded passages."""
    path = root / COUNTED
    if not path.is_file():
        return {}
    kept = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    counts = cast("list[dict[str, int]]", kept["counts"])
    if not counts:
        return {}
    found = {name: round(fmean(item[name] for item in counts), 4) for name in COUNTS}
    passages = sum(item["passages"] for item in counts)
    if passages:
        grounded = sum(item["passages_grounded"] for item in counts)
        found[GROUNDED] = round(grounded / passages, 4)
    return found
