"""The form of a blueprint, read from its text (evals/surface_evals/blueprint.py)."""

from pathlib import Path

import pytest
import toy

from surface_evals.blueprint import (
    CLOSING,
    LEAD_IN,
    OPENING,
    Statement,
    parse,
    says_none,
    statement,
)
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


def test_the_closing_section_of_the_template_opens_on_the_lead_in_the_harness_looks_for() -> None:
    assert parse(TEMPLATE.read_text(encoding="utf-8")).zones.startswith(f"{LEAD_IN}, among those")


def test_the_sentence_a_closing_section_opens_on_states_the_zones_and_their_files() -> None:
    lead = "Critical zones touched, among those `AGENTS.md` declares:"
    # None, and nothing announced, whatever the page says after its first sentence.
    none = f"{lead} none. The plan does not change `lending/fines.py` (criterion 9)."
    assert statement(none, ZONES) == Statement(none=True, files=())
    # Each zone with in backticks its files the plan changes. A full stop inside a path ends
    # no sentence, and the word the host names a zone with is no file the page announces.
    touched = (
        f"{lead} the fine computation, in `lending/fines.py` and `lending/__main__.py`, and the"
        " format of `loans.jsonl`, in `lending/loans.py`. In `lending/fines.py` the plan changes"
        " only how the file loads the loans module, and no critical zone rule changes: `README.md`"
        " is not a file of a zone."
    )
    files = ("lending/fines.py", "lending/__main__.py", "lending/loans.py")
    assert statement(touched, ZONES) == Statement(none=False, files=files)
    assert not says_none(touched, ZONES)
    # The lead-in may hold a full stop or a file of its own: the statement follows its colon.
    assert statement("Critical zones touched (i.e. in `AGENTS.md`): none.", ZONES) == Statement(
        none=True, files=()
    )
    # A sentence that runs to the end of the paragraph, on two lines, is read whole.
    wrapped = f"{lead} the fine computation,\nin `lending/fines.py`\n\nThe mailer changes."
    assert statement(wrapped, ZONES) == Statement(none=False, files=("lending/fines.py",))


@pytest.mark.parametrize(
    "zones",
    [
        "The plan touches no critical zone.",
        "**Critical zones**. None is touched.",
        "Critical zone touched: the CSV export (`AGENTS.md`).",
        "Critical zones touched by the plan are none.",
        "Critical zones touched, among those `AGENTS.md` declares:\n\n- The fine computation.",
        "Critical zones touched, among those `AGENTS.md` declares:\n- The fine computation.",
        "",
    ],
)
def test_a_section_that_opens_otherwise_is_outside_the_form(zones: str) -> None:
    assert statement(zones, ZONES) is None


# What a page may write to say that the plan touches no critical zone, and what it writes of a
# zone it touches that holds the same words: in the form, read by its first sentence, and
# outside it, read as free prose.
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
