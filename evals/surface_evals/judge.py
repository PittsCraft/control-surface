"""Is the chain good to work with: judged by a model against the written rubric.

The rubric, `evals/judge/rubric.md`, is cut in dimensions, each with the documents the judge
reads and its criteria. The judge gives each criterion a score from 1 to 5, its reason and the
passage the score rests on. The script holds what a script can: an answer that is not the form
asked for is refused, and a passage that is in no document is marked as not grounded.
"""

import json
import re
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import cast

from surface_evals import HOST, JUDGE
from surface_evals.budget import Ledger
from surface_evals.corpus import Case
from surface_evals.runner import RECORD, stops_at_hand_over
from surface_evals.sessions import ask

MODEL = "opus"
RUBRIC = JUDGE / "rubric.md"
VERDICTS = "judge.json"
LOWEST, HIGHEST = 1, 5
CODE_TOOLS = ("Read", "Glob", "Grep")
SAID_LIMIT = 600  # characters of what the developer said, kept in the timeline of the stops
MISSING = "(none)"  # what stands for a document a run did not leave
# The documents that tell a run to its end: a run that stopped at the hand over holds only
# their part of planning, where the interview and the blueprint are whole.
TO_THE_END = frozenset({"stops", "pr-body"})
IN_PLANNING = "-in-planning"
STOPPED_AT_HAND_OVER = (
    "This run was played to the hand over of the blueprint and no further, on purpose: nothing"
    " was approved and nothing was built. Judge what you are given as it stood then, and fault"
    " nothing for a step that comes after."
)

_DIMENSION = re.compile(r"## (?P<id>[a-z-]+): (?P<title>.+)")
_READS = re.compile(r"Reads: (?P<documents>.+)")
_CRITERION = re.compile(r"- \*\*(?P<id>[a-z-]+)\*\*: (?P<text>.+)")
_NAME = re.compile(r"`(?P<name>[a-z-]+)`")
_SPACES = re.compile(r"\s+")


class JudgeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Dimension:
    id: str
    title: str
    text: str  # its part of the rubric, as written
    reads: tuple[str, ...]  # the documents the judge is given
    code: bool  # whether the judge may read the code of the host, as it was before the feature
    criteria: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Judgement:
    dimension: str
    criterion: str
    score: int
    reason: str
    passage: str
    grounded: bool  # the passage stands, word for word, in a document the judge was given


def load_rubric(path: Path = RUBRIC) -> tuple[str, tuple[Dimension, ...]]:
    """Read the rubric: what holds for every dimension, then each dimension."""
    head, *parts = re.split(r"^(?=## )", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    dimensions: list[Dimension] = []
    for part in parts:
        lines = part.splitlines()
        heading = _DIMENSION.fullmatch(lines[0])
        reads = next((found for line in lines if (found := _READS.fullmatch(line))), None)
        criteria = tuple(found["id"] for line in lines if (found := _CRITERION.match(line)))
        if heading is None or reads is None or not criteria:
            message = f"rubric: {lines[0]!r} is not a dimension with its documents and criteria"
            raise JudgeError(message)
        names = tuple(found["name"] for found in _NAME.finditer(reads["documents"]))
        dimensions.append(
            Dimension(
                id=heading["id"],
                title=heading["title"],
                text=part.strip(),
                reads=tuple(name for name in names if name != "code"),
                code="code" in names,
                criteria=criteria,
            )
        )
    return head.strip(), tuple(dimensions)


def in_planning(dimension: Dimension) -> Dimension:
    """Give the dimension a run that stopped at the hand over is judged on.

    A dimension that reads the interview and the blueprint is asked as it is: its scores compare
    with those of a run played whole. One that reads the stops is asked of planning alone,
    which is another question: it is told so, and takes another name, so that its scores never
    join those of the runs played whole.
    """
    if TO_THE_END.isdisjoint(dimension.reads):
        return dimension
    return replace(
        dimension,
        id=f"{dimension.id}{IN_PLANNING}",
        text=f"{dimension.text}\n\n{STOPPED_AT_HAND_OVER}",
    )


def prompt(dimension: Dimension, documents: Mapping[str, str]) -> str:
    """Write what the judge is asked for one dimension: its rubric, the documents, the form."""
    given = "\n\n".join(
        f'<document name="{name}">\n{documents[name].strip()}\n</document>'
        for name in dimension.reads
    )
    code = (
        "\n\nThe code of the project, as it was before the feature, is in your working directory:"
        " read there, and nowhere else, what a criterion asks you to check in the code."
        if dimension.code
        else ""
    )
    form = (
        '{"judgements": [{"criterion": "<its name>", "score": 3,'
        ' "reason": "<two sentences at most>",'
        ' "passage": "<copied word for word from one document>"}]}'
    )
    return (
        f"{dimension.text}\n\n## The documents\n\n{given}{code}\n\n## Your answer\n\n"
        f"One JSON object and nothing else, one judgement per criterion, in the order of the"
        f" rubric ({', '.join(dimension.criteria)}), each score a whole number from 1 to 5, in"
        f" this form:\n\n{form}\n"
    )


def flat(text: str) -> str:
    return _SPACES.sub(" ", text).strip()


def parse(answer: str, dimension: Dimension, documents: Mapping[str, str]) -> list[Judgement]:
    """Read the judge's answer, refusing one that is not a judgement of each criterion."""
    start, end = answer.find("{"), answer.rfind("}")
    try:
        raw = cast("dict[str, object]", json.loads(answer[start : end + 1]))
        given = cast("list[dict[str, object]]", raw["judgements"])
        criteria = tuple(str(item["criterion"]) for item in given)
    except (ValueError, KeyError, TypeError) as error:
        message = f"{dimension.id}: the answer is not the JSON object asked for: {error}"
        raise JudgeError(message) from error
    if criteria != dimension.criteria:
        message = f"{dimension.id}: judged {criteria}, the rubric asks {dimension.criteria}"
        raise JudgeError(message)
    texts = [flat(documents[name]) for name in dimension.reads]
    judgements: list[Judgement] = []
    for item in given:
        score = item.get("score")
        if isinstance(score, str) and score.strip().isdecimal():
            score = int(score)  # a number written as a text is the number
        if type(score) is not int or not LOWEST <= score <= HIGHEST:
            message = f"{dimension.id}: {item['criterion']} has the score {score!r}, not 1 to 5"
            raise JudgeError(message)
        passage = flat(str(item.get("passage", "")))
        judgements.append(
            Judgement(
                dimension=dimension.id,
                criterion=str(item["criterion"]),
                score=score,
                reason=flat(str(item.get("reason", ""))),
                passage=passage,
                grounded=bool(passage) and any(passage in text for text in texts),
            )
        )
    return judgements


def timeline(record: Mapping[str, object]) -> str:
    """Tell a run as the developer lived it: what they said, then where each session stopped."""
    told: list[str] = []
    stops = cast("list[dict[str, object]]", record["stops"])
    for number, stop in enumerate(stops, start=1):
        said = str(stop["said"])
        if len(said) > SAID_LIMIT:
            said = said[:SAID_LIMIT] + " [...]"
        told.append(
            f"### Stop {number}\n\nThe developer said ({stop['kind']}):\n\n{said}\n\n"
            f"The session ended with the plan in the state `{stop['state']}`, on this message:\n\n"
            f"{stop['final']}"
        )
    return "\n\n".join(told)


def documents_of(root: Path, case: Case) -> dict[str, str]:
    """Gather the documents of a run a judge may be given, by the names the rubric uses."""
    record = cast("dict[str, object]", json.loads((root / RECORD).read_text(encoding="utf-8")))
    folder = root / str(record["project"]) / str(record["plan"] or "")
    documents = {"need": case.need, "stops": timeline(record)}
    for name, path in (
        ("interview", folder / "interview.md"),
        ("blueprint", folder / "blueprint.md"),
        ("pr-body", root / "pr-body.md"),
    ):
        documents[name] = path.read_text(encoding="utf-8") if path.is_file() else MISSING
    return documents


def judge(  # noqa: PLR0913 (what one judgement is given, each by its name)
    dimension: Dimension,
    documents: Mapping[str, str],
    log: Path,
    *,
    system: str,
    model: str,
    ledger: Ledger,
    code: Path = HOST,
) -> list[Judgement]:
    """Have the judge score one dimension, in a folder that holds the code and nothing else."""
    with tempfile.TemporaryDirectory() as scratch:
        workdir = Path(scratch) / "project"
        if dimension.code:
            shutil.copytree(code, workdir, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        else:
            workdir.mkdir()
        session = ask(
            prompt(dimension, documents),
            log,
            system=system,
            model=model,
            cwd=workdir,
            tools=CODE_TOOLS if dimension.code else (),
        )
    ledger.note(session)
    return parse(session.final, dimension, documents)


def judge_run(root: Path, case: Case, *, model: str, repeats: int, ledger: Ledger) -> Path:
    """Judge a run on every dimension, `repeats` times, and keep the verdicts in its folder."""
    system, dimensions = load_rubric()
    if stops_at_hand_over(root):
        dimensions = tuple(in_planning(dimension) for dimension in dimensions)
    documents = documents_of(root, case)
    verdicts: list[dict[str, object]] = []
    refused: list[str] = []
    for repeat in range(1, repeats + 1):
        for dimension in dimensions:
            if ledger.exhausted() is not None:
                break
            log = root / "logs-judge" / f"{dimension.id}-{repeat:02d}.jsonl"
            try:
                found = judge(dimension, documents, log, system=system, model=model, ledger=ledger)
            except JudgeError as error:
                refused.append(str(error))
                continue
            verdicts.extend({**asdict(judgement), "repeat": repeat} for judgement in found)
    kept = {"v": 1, "model": model, "judgements": verdicts, "refused": refused}
    path = root / VERDICTS
    path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
    return path
