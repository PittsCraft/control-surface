"""The form of a blueprint, read from its text (evals/surface_evals/blueprint.py)."""

from pathlib import Path

import pytest
import toy

from surface_evals.blueprint import CLOSING, OPENING, parse, says_none
from surface_evals.measure import ZONES

TEMPLATE = Path(__file__).resolve().parents[2] / "skills/surface-plan/templates/blueprint.md"


def test_the_frame_is_the_one_of_the_template_the_extractor_is_given() -> None:
    template = parse(TEMPLATE.read_text(encoding="utf-8"))
    assert template.titles[: len(OPENING)] == OPENING
    assert template.titles[-1] == CLOSING
    assert template.framed
    assert len(template.body) == 1
    assert template.numbered == ()
    assert template.closing_line == "<the aspects the plan leaves alone, by name>."


def test_the_toys_blueprint_has_one_section_in_its_body_and_one_diagram() -> None:
    drawn = parse(toy.BLUEPRINT)
    assert drawn.framed
    assert [section.title for section in drawn.body] == ["The export command"]
    assert drawn.diagrams == 1
    assert drawn.body[0].diagrams == 1
    assert drawn.criteria == 6
    assert drawn.closing_line == "state machines."
    assert "Critical zone touched: the CSV export" in drawn.zones


def test_a_blueprint_without_its_frame_is_told_and_all_its_sections_are_its_body() -> None:
    drawn = parse("# Title\n\n## 1. The idea\n\nIt.\n\n## 2. Data\n\nA table.\n")
    assert not drawn.framed
    assert drawn.numbered == ("1. The idea", "2. Data")
    assert len(drawn.body) == 2
    assert drawn.closing_line is None
    assert drawn.criteria == 0


def test_a_heading_inside_a_fence_is_not_a_section() -> None:
    text = "## One\n\n```text\n## not a heading\n```\n\n```mermaid\nflowchart LR\n  a --> b\n```\n"
    drawn = parse(text)
    assert drawn.titles == ("One",)
    assert drawn.diagrams == 1
    assert drawn.words > 0


def test_a_title_in_bold_at_the_head_of_a_paragraph_is_counted_inside_its_section() -> None:
    text = (
        "## A run\n\n"
        "**Who is skipped.** A member reminded less than 7 days ago.\n\n"
        "    M2 2 1.00\n\n"
        "| book | due |\n|---|---|\n| B1 | 2026-03-15 |\n\n"
        "```text\n**not a title**\n\nstill the fence\n```\n\n"
        "- **An item** of a list is no title.\n\n"
        "**What is printed.** One line per member.\nIt goes on.\n"
    )
    section = parse(text).body[0]
    # Two paragraphs and a list: the table and the blocks of code are no prose.
    assert len(section.paragraphs) == 3
    assert section.inner_titles == 2
    assert not section.untitled_and_long


def test_a_section_longer_than_a_glance_with_no_title_is_told() -> None:
    long = parse("## A run\n\nOne.\n\nTwo.\n\nThree.\n").body[0]
    assert long.untitled_and_long
    # Two paragraphs are taken in at a glance: no title is missed there.
    short = parse("## A run\n\nOne.\n\n```mermaid\nflowchart LR\n```\n\nTwo.\n").body[0]
    assert not short.untitled_and_long
    assert short.inner_titles == 0


# What a page may write to say that the plan touches no critical zone, and what it writes of a
# zone it touches that holds the same words.
SAYS_NONE = (
    "Critical zones touched, among those `AGENTS.md` declares: none.",
    "Critical zones touched (i.e. among those `AGENTS.md` declares): none.",
    (
        "**Critical zones**. None is touched: the fine computation and the format of"
        " `loans.jsonl` stay as they are."
    ),
    (
        "The plan changes `lending/reports.py` and its tests. None of them holds the code of a"
        " critical zone."
    ),
    "Of the critical zones that `AGENTS.md` declares, the plan touches none.",
    (
        "The plan touches neither of the two critical zones that `AGENTS.md` declares: the fine"
        " computation (`lending/fines.py`) and the format of `loans.jsonl`."
    ),
    "The command only reads `loans.jsonl`, and the plan touches none of the critical zones.",
    (
        "Critical zones touched: none. The fine computation (`lending/fines.py`) is called, not"
        " changed."
    ),
    "The plan touches no critical zone.",
)
NAMES_A_ZONE = (
    (
        "Critical zones touched: the format of `loans.jsonl`, through `lending/loans.py`, which"
        " changes none of its fields."
    ),
    (
        "Critical zones touched: the fine computation, through `lending/__main__.py`, which"
        " neither computes nor rounds the fine."
    ),
    (
        "Critical zones touched, among those `AGENTS.md` declares: the format of `loans.jsonl`,"
        " through `lending/loans.py`. The plan changes only the borrow check in that file and"
        " touches none of the fields of a loan line: the zone is touched, its rule is not."
    ),
    (
        "The plan touches the fine computation (`lending/fines.py`), a critical zone: its rules"
        " are criteria 1 to 8."
    ),
    "Critical zones touched, among those `AGENTS.md` declares:",
)


@pytest.mark.parametrize("statement", SAYS_NONE)
def test_a_page_says_none_outright_or_before_it_names_any_zone(statement: str) -> None:
    assert says_none(statement, ZONES)
    # Only the paragraph that opens the section states it: what follows says something else.
    assert says_none(f"{statement}\n\nThe mailer finds a new kind of notice.", ZONES)


@pytest.mark.parametrize("statement", NAMES_A_ZONE)
def test_a_none_that_says_how_far_the_plan_goes_into_a_zone_is_not_the_statement(
    statement: str,
) -> None:
    assert not says_none(statement, ZONES)
    assert not says_none(f"{statement}\n\nNone of the mailer changes.", ZONES)
