"""The form of a blueprint, read from its text (evals/surface_evals/blueprint.py)."""

from pathlib import Path

import toy

from surface_evals.blueprint import CLOSING, OPENING, parse

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
