"""The count of a blueprint, beside the scores of the judge (evals/surface_evals/count.py)."""

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

import pytest
from support import case, kept_run

from surface_evals import CASES, REPORTS, cli, count, judge, judge_check
from surface_evals.budget import Ledger
from surface_evals.count import (
    BESIDE,
    COUNTED,
    COUNTS,
    GROUNDED,
    PLACES,
    Count,
    Detail,
    Fact,
    Statement,
    count_run,
    counts_of,
    load,
    parse,
    prompt,
)
from surface_evals.judge import JudgeError, load_rubric
from surface_evals.report import compare, render, summarize, uncompared, write
from surface_evals.runner import STOPPED
from surface_evals.sessions import SessionLog

PAGE = """\
# Overdue list: blueprint

## The idea in one sentence

A command lists the loans past their due date.

## Acceptance criteria

1. `overdue` prints one line per late loan.
2. The latest comes first.

## Scope and out of scope

Out of scope: reminders.

## The overdue command

The command prints one line for each late loan, the latest first. The helper `late_first` in
`cli.py` sorts them.

```mermaid
flowchart TD
  L[loans] --> O[one line per late loan]
```

## Sensitive zones

Critical zones touched: none.
"""
FACTS: list[dict[str, object]] = [
    {
        "fact": "one line per late loan",
        "statements": [
            {"place": "criteria", "passage": "`overdue` prints one line per late loan."},
            {"place": "body", "passage": "The command prints one line\nfor each late loan"},
            {"place": "diagram", "passage": "O[one line per late loan]"},
        ],
    },
    {
        "fact": "the latest first",
        "statements": [
            {"place": "criteria", "passage": "The latest comes first."},
            {"place": "Diagram", "passage": "the latest on top"},
        ],
    },
]
DETAILS: list[dict[str, object]] = [
    {"detail": "the helper late_first", "passage": "The helper `late_first` in `cli.py`"}
]
NOTHING = json.dumps(
    {
        "repeated_facts": [],
        "implementation_details": [],
        "skippable_percent": 0,
        "would_skip": "Nothing.",
    }
)
# The first campaign kept: judged before the judge counted, so its summary holds no count.
OLD = REPORTS / "2026-10-03-6bf7c06609a6" / "summary.json"
OLD_CASE = "01-overdue-list"


def _answer(**changes: object) -> str:
    given: dict[str, object] = {
        "repeated_facts": FACTS,
        "implementation_details": DETAILS,
        "skippable_percent": 30,
        "would_skip": "The second half of the body.",
    }
    kept = {key: value for key, value in {**given, **changes}.items() if value is not None}
    return "Here is the count.\n" + json.dumps(kept)


def _count(repeated: int, details: int, share: int, *, grounded: bool = True) -> Count:
    """Make a count of that many facts said twice in prose, details, and percent to skip."""
    twice = (Statement("criteria", "a rule", grounded), Statement("body", "the rule", grounded))
    return Count(
        facts=tuple(Fact(f"fact {number}", twice) for number in range(repeated)),
        details=tuple(
            Detail(f"detail {number}", "a helper", grounded=True) for number in range(details)
        ),
        skippable_percent=share,
        would_skip="The body.",
    )


def _keep(root: Path, *counts: Count) -> Path:
    """Write the counts of a run as `count_run` keeps them."""
    listed = [{"repeat": repeat, **found.kept()} for repeat, found in enumerate(counts, start=1)]
    kept = {"v": 1, "model": "opus", "counts": listed, "refused": []}
    (root / COUNTED).write_text(json.dumps(kept), encoding="utf-8")
    return root


class Reader:
    """Stands for the session of a count: it answers as told, and keeps what it was asked."""

    def __init__(self, answer: Callable[[str], str]) -> None:
        self.answer = answer
        self.asked: list[tuple[str, str, str]] = []

    def __call__(  # noqa: PLR0913 (the keywords of the call it stands for)
        self,
        asked: str,
        log: Path,
        *,
        system: str,
        model: str,
        cwd: Path,
        tools: Sequence[str] = (),
    ) -> SessionLog:
        # The reader is given the page alone: no tool, and a folder that holds nothing.
        assert not tools
        assert not list(cwd.iterdir())
        self.asked.append((system, model, asked))
        return SessionLog(
            path=log,
            session_id=f"count-{len(self.asked)}",
            ended=True,
            final=self.answer(asked),
            cost=0.25,
            gauges=(),
            launches=(),
        )


def test_the_method_names_what_is_counted_and_every_place_a_statement_may_stand_in() -> None:
    system, asked = load()
    assert "The developer reads all of it" in system
    assert "This is a measurement, not a judgement" in system
    assert asked.startswith("## What to count")
    assert "List every fact the page states more than once" in asked
    assert "copied word for word from the page" in asked
    assert "Details of implementation that are not the developer's to decide" in asked
    assert "in percent of its words" in asked
    for place in PLACES:
        assert f"`{place}`" in asked
    # A count, beside the scores: the method gives no scale, and the rubric is asked as before.
    assert "score" not in system + asked
    head, dimensions = load_rubric()
    assert BESIDE == ("blueprint", "no-padding")
    assert BESIDE[1] in next(found.criteria for found in dimensions if found.id == BESIDE[0])
    assert "word for word from the page" not in head + "".join(found.text for found in dimensions)


def test_a_method_that_does_not_say_what_to_count_is_refused(tmp_path: Path) -> None:
    (tmp_path / "count.md").write_text("# Count\n\nYou measure a page.\n", encoding="utf-8")
    with pytest.raises(JudgeError):
        load(tmp_path / "count.md")


def test_the_reader_is_given_the_method_the_page_alone_and_the_form_of_its_answer() -> None:
    _, asked = load()
    told = prompt(asked, PAGE)
    assert told.startswith(asked)
    assert f'<document name="blueprint">\n{PAGE.strip()}\n</document>' in told
    assert told.count("<document ") == 1
    assert "One JSON object and nothing else" in told
    assert "no total" in told
    for key in (
        "repeated_facts",
        "fact",
        "statements",
        "place",
        "passage",
        "implementation_details",
        "detail",
        "skippable_percent",
        "would_skip",
    ):
        assert f'"{key}":' in told


def test_the_totals_are_counted_from_the_lists_and_a_diagram_is_not_a_repeat_in_prose() -> None:
    found = parse(_answer(), PAGE)
    said, drawn = found.facts
    # Said in a criterion and in the body: twice in prose. The other one is only drawn again.
    assert (said.fact, said.in_prose) == ("one line per late loan", True)
    assert [stated.place for stated in said.statements] == ["criteria", "body", "diagram"]
    assert (drawn.in_prose, drawn.statements[1].place) == (False, "diagram")
    assert found.numbers == {
        "repeated_in_prose": 1,
        "implementation_details": 1,
        "skippable_percent": 30,
    }
    assert tuple(found.numbers) == COUNTS
    assert found.would_skip == "The second half of the body."
    kept = found.kept()
    assert (kept["repeated_in_prose"], kept["passages"], kept["passages_grounded"]) == (1, 6, 5)
    assert json.loads(json.dumps(kept))["facts"][0]["statements"][0] == {
        "place": "criteria",
        "passage": "`overdue` prints one line per late loan.",
        "grounded": True,
    }


def test_a_passage_only_a_diagram_holds_is_a_statement_in_a_diagram_whatever_its_place() -> None:
    line = "L[loans] --> O[one line per late loan]"
    called = [
        {
            "fact": "one line per late loan",
            "statements": [
                {"place": "criteria", "passage": "`overdue` prints one line per late loan."},
                {"place": "body", "passage": line},
            ],
        },
        {
            "fact": "the loans are read",
            "statements": [
                # Words the prose and the diagram both hold: the place given is all there is.
                {"place": "criteria", "passage": "one line per late loan"},
                {"place": "body", "passage": "one line per late loan"},
                # A passage that is nowhere cannot be placed either.
                {"place": "body", "passage": "L[loans] --> O[every loan]"},
            ],
        },
    ]
    drawn, kept = parse(_answer(repeated_facts=called), PAGE).facts
    # A diagram's line called prose would make a repeat in prose of what is only drawn again.
    assert [stated.place for stated in drawn.statements] == ["criteria", "diagram"]
    assert not drawn.in_prose
    assert [stated.place for stated in kept.statements] == ["criteria", "body", "body"]
    assert [stated.grounded for stated in kept.statements] == [True, True, False]
    # A fence that is not a diagram is prose: an example, a command.
    fenced = PAGE.replace("```mermaid", "```text")
    assert parse(_answer(repeated_facts=called), fenced).facts[0].in_prose


def test_a_passage_that_is_not_on_the_page_is_marked() -> None:
    found = parse(_answer(), PAGE)
    said, drawn = found.facts
    # A passage copied across a line break is the passage.
    assert [stated.grounded for stated in said.statements] == [True, True, True]
    assert [stated.grounded for stated in drawn.statements] == [True, False]
    assert found.details[0].grounded
    missing = parse(_answer(implementation_details=[{"detail": "a constant"}]), PAGE)
    assert (missing.details[0].passage, missing.details[0].grounded) == ("", False)
    # The same passage given twice is two statements only where the page holds it twice.
    once = {"place": "criteria", "passage": "The latest comes first."}
    twice = {"place": "body", "passage": "one line per late loan"}
    again = parse(
        _answer(
            repeated_facts=[
                {"fact": "the latest first", "statements": [once, once]},
                {"fact": "one line per late loan", "statements": [twice, twice]},
            ]
        ),
        PAGE,
    )
    assert [stated.grounded for stated in again.facts[0].statements] == [True, False]
    assert [stated.grounded for stated in again.facts[1].statements] == [True, True]


def test_a_page_with_nothing_to_skip_counts_zero() -> None:
    found = parse(NOTHING, PAGE)
    assert found.numbers == dict.fromkeys(COUNTS, 0)
    assert (found.kept()["passages"], found.kept()["passages_grounded"]) == (0, 0)


@pytest.mark.parametrize(("share", "read"), [("35", 35), (" 35% ", 35), (100, 100)])
def test_a_share_written_as_a_text_is_the_number(share: object, read: int) -> None:
    assert parse(_answer(skippable_percent=share), PAGE).skippable_percent == read


@pytest.mark.parametrize(
    "answer",
    [
        "I cannot count this.",
        _answer(repeated_facts=None),
        _answer(repeated_facts="none"),
        _answer(repeated_facts=["one line per late loan"]),
        _answer(repeated_facts=[{"fact": "said once", "statements": ()}]),
        _answer(repeated_facts=[{"fact": "said once", "statements": "in the body"}]),
        _answer(
            repeated_facts=[
                {"fact": "said once", "statements": [{"place": "body", "passage": "The command"}]}
            ]
        ),
        _answer(
            repeated_facts=[
                {
                    "statements": [
                        {"place": "criteria", "passage": "The latest comes first."},
                        {"place": "body", "passage": "the latest first"},
                    ]
                }
            ]
        ),
        _answer(
            repeated_facts=[
                {
                    "fact": "the latest first",
                    "statements": [
                        {"place": "criteria", "passage": "The latest comes first."},
                        {"place": "appendix", "passage": "the latest first"},
                    ],
                }
            ]
        ),
        _answer(implementation_details=None),
        _answer(implementation_details=["late_first"]),
        _answer(implementation_details=[{"passage": "The helper `late_first`"}]),
        _answer(skippable_percent=None),
        _answer(skippable_percent=130),
        _answer(skippable_percent=-5),
        _answer(skippable_percent=12.5),
        _answer(skippable_percent="a third"),
    ],
)
def test_an_answer_that_is_not_the_lists_and_the_share_asked_for_is_refused(answer: str) -> None:
    with pytest.raises(JudgeError):
        parse(answer, PAGE)


def _padded_count() -> str:
    """Count the padded page of the judge's check by hand, as a reader of the method would."""
    facts = {
        "the need: a CSV for the bookshop's spreadsheet": [
            ("idea", "A new command prints the books of a shelf file as CSV"),
            ("body", "The bookshop wants to load our shelf into its spreadsheet."),
            ("body", "it lets the bookshop load the shelf into its spreadsheet"),
        ],
        "a header, then one line per book: title, author and year": [
            ("body", "The command prints a header line, then one line per book"),
            ("criteria", "One line per book: its title, author and year, in that order."),
            ("body", "the columns are the title, the author and the year, in this order"),
        ],
        "the ISBN is not exported": [
            ("criteria", "The ISBN is not exported."),
            ("body", "the ISBN is not one of them"),
        ],
        "the lines are sorted by author, then by title": [
            ("criteria", "The lines are sorted by author, then by title."),
            ("body", "its lines are sorted by author, then by title"),
            ("body", "`sorted(books, key=lambda book: (book.author, book.title))`"),
        ],
        "lines end with a line feed": [
            ("body", "Lines end with a line feed"),
            ("body", 'with `lineterminator="\\n"`'),
        ],
        "the CSV goes to standard output, with the exit code 0": [
            ("criteria", "as CSV on standard output and exits with 0"),
            ("body", "`main` passes it to `sys.stdout.write`, then returns 0"),
            ("diagram", "C-->>D: CSV on standard output, exit 0"),
        ],
        "the books are loaded, sorted, written": [
            ("body", "A `for` loop goes over"),
            ("diagram", "C->>C: load the books, sort them, write the CSV"),
        ],
    }
    details = {
        "the argparse parser and its sub-parser": "builds an `argparse` parser",
        "the local variable books": "a local variable named `books`",
        "the buffer and the writer of to_csv": "creates an `io.StringIO` buffer named `out`",
        "the constant HEADER": "`HEADER` is a module constant",
        "the loop over the sorted books": "`writer.writerow((book.title, book.author, book.year))`",
        "what to_csv returns": "`to_csv` returns `out.getvalue()`",
        "the list of the tests": "The function `to_csv` gets unit tests in `tests/test_export.py`",
    }
    return json.dumps(
        {
            "repeated_facts": [
                {
                    "fact": fact,
                    "statements": [{"place": place, "passage": passage} for place, passage in said],
                }
                for fact, said in facts.items()
            ],
            "implementation_details": [
                {"detail": detail, "passage": passage} for detail, passage in details.items()
            ],
            "skippable_percent": 60,
            "would_skip": "The background, the walk through the code, the diagram and the tests.",
        }
    )


def test_the_padded_page_of_the_check_counts_in_the_form_asked_for_and_the_lean_one_does_not() -> (
    None
):
    (pair,) = (found for found in judge_check.load_pairs() if found.name == "padded-blueprint")
    assert (pair.dimension, pair.criterion) == BESIDE
    lean, padded = (
        judge_check.documents(pair, spoiled=spoiled)[pair.replaces] for spoiled in (False, True)
    )
    found = parse(_padded_count(), padded)
    # Six facts said more than once in prose and seven details, as a reader counted them by
    # hand, and here one fact that is only drawn again, which is listed and not counted. Every
    # passage stands on the page, a diagram's line and a quoted line ending included.
    assert found.numbers == {
        "repeated_in_prose": 6,
        "implementation_details": 7,
        "skippable_percent": 60,
    }
    kept = found.kept()
    assert kept["passages"] == kept["passages_grounded"] == 25
    # Held against the lean page, the same count rests on passages that are not there.
    elsewhere = parse(_padded_count(), lean).kept()
    assert cast("int", elsewhere["passages_grounded"]) < cast("int", elsewhere["passages"]) // 2
    assert parse(NOTHING, lean).numbers == dict.fromkeys(COUNTS, 0)


def test_the_blueprint_of_a_run_is_counted_and_an_answer_refused_is_kept_as_such(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter([_answer(), "I cannot count this.", _answer(skippable_percent=40)])
    reader = Reader(lambda _: next(answers))
    monkeypatch.setattr(count, "ask", reader)
    (tmp_path / "need.md").write_text("List the overdue loans.\n", encoding="utf-8")
    root = kept_run(tmp_path, journal=[], blueprints=(PAGE,))
    ledger = Ledger(path=tmp_path / "ledger.json")
    path = count_run(root, case(tmp_path), model="opus", repeats=3, ledger=ledger)
    assert path == root / COUNTED
    kept = json.loads(path.read_text(encoding="utf-8"))
    assert (kept["v"], kept["model"]) == (1, "opus")
    assert [found["repeat"] for found in kept["counts"]] == [1, 3]
    assert [found["skippable_percent"] for found in kept["counts"]] == [30, 40]
    assert kept["counts"][0]["facts"][1]["in_prose"] is False
    assert len(kept["refused"]) == 1
    assert "not the JSON object asked for" in kept["refused"][0]
    # Every session is paid for, the one whose answer is refused too.
    assert (ledger.sessions, ledger.usd) == (3, 0.75)
    # The reader was given the method and the page, and nothing else of the run.
    system, model, asked = reader.asked[0]
    assert (system, model) == (load()[0], "opus")
    assert PAGE.strip() in asked
    assert "List the overdue loans." not in asked
    # Folded for the report: the mean of each measure, and the share of grounded passages.
    assert counts_of(root) == {
        "repeated_in_prose": 1.0,
        "implementation_details": 1.0,
        "skippable_percent": 35.0,
        GROUNDED: round(10 / 12, 4),
    }


def test_a_run_that_handed_no_blueprint_over_keeps_no_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = Reader(lambda _: NOTHING)
    monkeypatch.setattr(count, "ask", reader)
    (tmp_path / "need.md").write_text("List the overdue loans.\n", encoding="utf-8")
    root = kept_run(tmp_path, journal=[])
    (root / "work" / "lending" / "docs" / "plans" / "2026-01-15-overdue" / "blueprint.md").unlink()
    path = count_run(
        root, case(tmp_path), model="opus", repeats=2, ledger=Ledger(path=tmp_path / "ledger.json")
    )
    # No session, and no zero that would read as a page with nothing to skip.
    assert reader.asked == []
    assert json.loads(path.read_text(encoding="utf-8"))["counts"] == []
    assert counts_of(root) == {}
    assert counts_of(tmp_path / "elsewhere") == {}


def test_the_count_is_checked_on_the_padded_page_which_must_count_more_than_the_lean_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pairs = judge_check.load_pairs()
    ledger = Ledger(path=tmp_path / "ledger.json")
    padded = Reader(lambda asked: _padded_count() if "## Background" in asked else NOTHING)
    monkeypatch.setattr(count, "ask", padded)
    results, refused = judge_check.check_counts(
        pairs, tmp_path / "logs", model="opus", repeats=2, ledger=ledger
    )
    # One pair spoils the criterion the count stands beside: its two pages, twice each.
    assert len(padded.asked) == 4
    assert refused == []
    assert [(found["name"], found["count"]) for found in results] == [
        ("padded-blueprint", name) for name in COUNTS
    ]
    assert [(found["original"], found["spoiled"]) for found in results] == [
        ([0, 0], [6, 6]),
        ([0, 0], [7, 7]),
        ([0, 0], [60, 60]),
    ]
    assert all(found["above"] for found in results)
    # A reader that counts the same on both pages is one whose count is not to be trusted.
    monkeypatch.setattr(count, "ask", Reader(lambda _: _answer()))
    results, _ = judge_check.check_counts(
        pairs, tmp_path / "logs", model="opus", repeats=1, ledger=ledger
    )
    assert [found["above"] for found in results] == [False, False, False]
    # And one whose answers are all refused has shown nothing.
    monkeypatch.setattr(count, "ask", Reader(lambda _: "I cannot count this."))
    results, refused = judge_check.check_counts(
        pairs, tmp_path / "logs", model="opus", repeats=1, ledger=ledger
    )
    assert len(refused) == 2
    assert [(found["original"], found["above"]) for found in results] == [([], False)] * 3


def _campaign(out: Path, name: str, *counts: Count) -> Path:
    """Keep a campaign of one case, a run per count."""
    for number, found in enumerate(counts, start=1):
        _keep(kept_run(out / "runs" / name / f"run-{number:02d}", journal=[]), found)
    return out


def test_the_report_gives_the_counts_with_their_spread_and_says_what_moved(tmp_path: Path) -> None:
    name = min(path.name for path in CASES.iterdir() if (path / "case.json").is_file())
    made_up = [_count(14, 8, 40, grounded=False), _count(15, 9, 40, grounded=False)]
    before = _campaign(tmp_path / "before", name, *made_up)
    after = _campaign(tmp_path / "after", name, _count(2, 1, 10), _count(4, 1, 15))
    summary = summarize(after)
    cases = cast("dict[str, dict[str, dict[str, dict[str, float]]]]", summary["cases"])
    everything = cast("dict[str, dict[str, dict[str, float]]]", summary["all"])
    assert cases[name]["count"]["repeated_in_prose"] == {"mean": 3, "low": 2, "high": 4, "n": 2}
    assert everything["count"]["skippable_percent"] == {
        "mean": 12.5,
        "low": 10,
        "high": 15,
        "n": 2,
    }
    assert everything["count"][GROUNDED]["mean"] == 1
    kept, _ = write(before, None)
    _, report = write(after, kept)
    text = report.read_text(encoding="utf-8")
    assert "## What the developer would skip on the blueprint" in text
    assert "| `repeated_in_prose` | 3 (2 to 4) | 3 (2 to 4) |" in text
    assert "| `implementation_details` | 1 | 1 |" in text
    assert "| `skippable_percent` | 12.5 (10 to 15) | 12.5 (10 to 15) |" in text
    assert f"| `{GROUNDED}` | 1 | 1 |" in text
    # Fewer facts said twice, fewer details and less to skip: each is better when it falls.
    assert f"- `{name}` `repeated_in_prose`: 14.5 (14 to 15) then 3 (2 to 4), better." in text
    assert "- `all` `implementation_details`: 8.5 (8 to 9) then 1, better." in text
    assert "- `all` `skippable_percent`: 40 then 12.5 (10 to 15), better." in text
    assert "Not compared" not in text
    back = {
        move.measure: move.verdict
        for move in compare(summarize(before), summary)
        if move.scope == "all"
    }
    assert [back[measure] for measure in COUNTS] == ["worse", "worse", "worse"]
    # The share of grounded passages says how far to trust a count, not how good a page is.
    assert back[GROUNDED] == "moved"


def test_a_campaign_kept_before_the_count_is_compared_without_a_word_on_counts_that_moved(
    tmp_path: Path,
) -> None:
    old = cast("dict[str, object]", json.loads(OLD.read_text(encoding="utf-8")))
    assert "count" not in cast("dict[str, object]", old["all"])
    after = _campaign(tmp_path, OLD_CASE, _count(2, 1, 10))
    new = summarize(after)
    named = (*COUNTS, GROUNDED)
    assert [move for move in compare(new, old) if move.measure in named] == []
    assert [move for move in compare(old, new) if move.measure in named] == []
    told = "Not compared: the counts of the blueprint, which the campaign before does not hold."
    assert uncompared(new, old) == [told]
    assert uncompared(old, new) == [told.replace("the campaign before", "this campaign")]
    assert uncompared(new, new) == []
    assert uncompared(old, old) == []
    _, report = write(after, OLD)
    moved = report.read_text(encoding="utf-8").split("## What moved since the campaign before")[1]
    assert all(measure not in moved for measure in named)
    assert moved.rstrip().endswith(told)
    # With nothing else to tell, the report does not leave "nothing moved" to cover the counts.
    assert (
        render(new, [], uncompared(new, old))
        .rstrip()
        .endswith(f"Nothing lies outside the spread between runs.\n\n{told}")
    )
    # The report of the campaign kept before still reads, and says nothing of a count.
    again = render(old)
    assert "## The judge, checked" in again
    assert "would skip" not in again
    assert "| Count |" not in again


def test_the_report_says_whether_each_count_rose_on_the_padded_page(tmp_path: Path) -> None:
    summary = summarize(tmp_path)
    pair = {"name": "padded-blueprint", "what": "a padded blueprint"}
    rose = {"count": "repeated_in_prose", "original": [0, 0], "spoiled": [6, 7], "above": True}
    flat = {"count": "skippable_percent", "original": [5, 5], "spoiled": [5, 5], "above": False}
    summary["judge_check"] = {
        "v": 1,
        "model": "opus",
        "pairs": [],
        "counts": [{**pair, **rose}, {**pair, **flat}],
        "refused": [],
    }
    text = render(summary)
    assert "| Spoiled document | Count | Original | Spoiled | Above |" in text
    assert "| a padded blueprint | `repeated_in_prose` | [0, 0] | [6, 7] | yes |" in text
    assert "| a padded blueprint | `skippable_percent` | [5, 5] | [5, 5] | no |" in text


def test_judging_counts_the_runs_not_counted_yet_and_scores_no_run_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    name = min(path.name for path in CASES.iterdir() if (path / "case.json").is_file())
    root = kept_run(tmp_path / "runs" / name / "run-01", journal=[], blueprints=(PAGE,))
    # A run judged before the judge counted: its scores are kept, and must stay as they are.
    scores = json.dumps({"v": 1, "model": "opus", "judgements": [], "refused": []})
    (root / judge.VERDICTS).write_text(scores, encoding="utf-8")
    scored: list[Path] = []

    def judge_run(found: Path, *_: object, **__: object) -> Path:
        scored.append(found)
        return found / judge.VERDICTS

    monkeypatch.setattr(judge, "judge_run", judge_run)
    reader = Reader(lambda _: _answer())
    monkeypatch.setattr(count, "ask", reader)
    assert cli.main(["--out", str(tmp_path), "judge"]) == 0
    assert capsys.readouterr().out.splitlines() == [f"{name} run-01: counted"]
    assert scored == []
    assert (root / judge.VERDICTS).read_text(encoding="utf-8") == scores
    assert counts_of(root)["repeated_in_prose"] == 1
    # Counted, it is left alone, until both are asked for again.
    assert cli.main(["--out", str(tmp_path), "judge"]) == 0
    assert capsys.readouterr().out == ""
    assert len(reader.asked) == 1
    assert cli.main(["--out", str(tmp_path), "judge", "--again", "--repeats", "2"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"{name} run-01: judged",
        f"{name} run-01: counted",
    ]
    assert scored == [root]
    assert len(reader.asked) == 3


def test_a_run_stopped_at_the_hand_over_is_counted_like_any_other_and_joins_the_same_spread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    name = min(path.name for path in CASES.iterdir() if (path / "case.json").is_file())
    runs = tmp_path / "runs" / name
    kept_run(runs / "run-01", journal=[], blueprints=(PAGE,))
    # Played to the hand over and no further: nothing was built, and its blueprint is whole.
    stopped = kept_run(
        runs / "run-02",
        journal=[],
        blueprints=(PAGE,),
        outcome=STOPPED,
        stop_at_hand_over=True,
    )

    def judge_run(found: Path, *_: object, **__: object) -> Path:
        return found / judge.VERDICTS

    monkeypatch.setattr(judge, "judge_run", judge_run)
    answers = iter([_answer(), _answer(skippable_percent=40)])
    reader = Reader(lambda _: next(answers))
    monkeypatch.setattr(count, "ask", reader)
    assert cli.main(["--out", str(tmp_path), "judge"]) == 0
    assert f"{name} run-02: counted" in capsys.readouterr().out.splitlines()
    # The reader is asked the same of both: the page alone, with no word on where the run stopped.
    whole, at_hand_over = reader.asked
    assert whole == at_hand_over
    assert counts_of(stopped)["skippable_percent"] == 40
    summary = summarize(tmp_path)
    everything = cast("dict[str, object]", summary["all"])
    measures = cast("dict[str, dict[str, float]]", everything["measures"])
    counted = cast("dict[str, dict[str, float]]", everything["count"])
    assert everything["stopped_at_hand_over"] == 1
    # What the execution gives leaves the stopped run out. Its counts join those of the other
    # run, under the same names: a blueprint is read the same wherever its run stopped.
    assert measures["conformant"]["n"] == 1
    assert set(counted) == {*COUNTS, GROUNDED}
    assert all(counted[measure]["n"] == 2 for measure in counted)
    assert counted["skippable_percent"] == {"mean": 35, "low": 30, "high": 40, "n": 2}
    text = render(summary)
    assert "1 of these runs played planning alone" in text
    assert "| `skippable_percent` | 35 (30 to 40) | 35 (30 to 40) |" in text


def test_the_check_of_the_judge_says_whether_each_count_rose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def check(out: Path, **_: object) -> Path:
        counted = {"name": "padded-blueprint", "original": [0, 0]}
        kept = {
            "pairs": [{"name": "padded-blueprint", "original": [3], "spoiled": [2], "below": True}],
            "counts": [
                {**counted, "count": "repeated_in_prose", "spoiled": [6, 7], "above": True},
                {**counted, "count": "skippable_percent", "spoiled": [0, 0], "above": False},
            ],
        }
        path = out / judge_check.RECORD
        path.write_text(json.dumps(kept), encoding="utf-8")
        return path

    monkeypatch.setattr(judge_check, "check", check)
    assert cli.main(["--out", str(tmp_path), "judge-check"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "padded-blueprint: [2] against [3], below its original",
        "padded-blueprint, `repeated_in_prose`: [6, 7] against [0, 0], above its original",
        "padded-blueprint, `skippable_percent`: [0, 0] against [0, 0], NOT above its original",
    ]
