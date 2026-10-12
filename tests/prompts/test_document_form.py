"""The pages a person reads stay readable: a bound on each paragraph, and one on each page.

A page that only ever gains sentences grows inside its paragraphs, where a diff shows one line
changed. The bounds make that growth fail a gate, and the way out is in `AGENTS.md`: cut by
subject, or move out what the page does not hold. This reads sizes, never a sentence (ADR 0032).
"""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_repo_text import ROOT

# Bytes, for a paragraph, a list item or a table row.
PARAGRAPH_BOUND = 600
# Bytes, for a page. Only the developer raises a bound (AGENTS.md).
PAGE_BOUNDS = {"ARCHITECTURE.md": 28_300}

_FENCE = "```"
_HEADING = re.compile(r"#{1,6} ")
# A list item or a table row starts a block of its own, even right under another line.
_STARTS_A_BLOCK = re.compile(r"\s*(?:[-*+] |[0-9]+\. |\|)")


def blocks(text: str) -> list[tuple[int, str]]:
    """Return each paragraph, list item and table row with its first line, fences left out.

    A paragraph wrapped over several lines is one block: wrapping it shortens nothing a reader
    reads.
    """
    found: list[tuple[int, list[str]]] = []
    fenced = False
    open_block = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
            open_block = False
        elif fenced or not line.strip() or _HEADING.match(line):
            open_block = False
        elif open_block and not _STARTS_A_BLOCK.match(line):
            found[-1][1].append(line.strip())
        else:
            found.append((number, [line.strip()]))
            open_block = True
    return [(number, " ".join(lines)) for number, lines in found]


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def over_the_bound(text: str, bound: int) -> list[tuple[int, int]]:
    """Return the first line and the size of each block over the bound."""
    return [(number, size(block)) for number, block in blocks(text) if size(block) > bound]


@pytest.mark.parametrize("page", sorted(PAGE_BOUNDS))
def test_no_paragraph_of_a_bounded_page_is_over_the_bound(page: str) -> None:
    long = over_the_bound((ROOT / page).read_text(encoding="utf-8"), PARAGRAPH_BOUND)
    assert not long, (
        f"{page}: (line, bytes) of each paragraph over {PARAGRAPH_BOUND} bytes: {long}."
        " Cut it by subject, or move out what the page does not hold (AGENTS.md)."
    )


@pytest.mark.parametrize(("page", "bound"), sorted(PAGE_BOUNDS.items()))
def test_no_bounded_page_is_over_its_bound(page: str, bound: int) -> None:
    held = size((ROOT / page).read_text(encoding="utf-8"))
    assert held <= bound, (
        f"{page} holds {held} bytes, over {bound}."
        " Cut or move before adding (AGENTS.md): only the developer raises a bound."
    )


def test_a_fence_and_a_heading_are_no_paragraph() -> None:
    text = "# A title\n\nOne.\n\n```text\nnot read\n```\n\nTwo.\n"
    assert blocks(text) == [(3, "One."), (9, "Two.")]


def test_a_list_item_and_a_table_row_are_read_one_by_one() -> None:
    text = "Lead:\n- first\n  - nested\n1. numbered\n\n| a | b |\n|---|---|\n"
    assert blocks(text) == [
        (1, "Lead:"),
        (2, "- first"),
        (3, "- nested"),
        (4, "1. numbered"),
        (6, "| a | b |"),
        (7, "|---|---|"),
    ]


def test_a_wrapped_paragraph_is_one_block() -> None:
    assert blocks("one\ntwo\n\n- item\n  goes on\n") == [(1, "one two"), (4, "- item goes on")]


@given(st.integers(min_value=1, max_value=2 * PARAGRAPH_BOUND))
def test_a_paragraph_is_found_from_one_byte_over_the_bound(length: int) -> None:
    text = f"Short.\n\n{'a' * length}\n"
    expected = [(3, length)] if length > PARAGRAPH_BOUND else []
    assert over_the_bound(text, PARAGRAPH_BOUND) == expected
