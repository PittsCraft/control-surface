"""Every pointer to a decision resolves: to a record that exists, or to an architecture section.

Records are removed when they no longer meet the criteria, and `ARCHITECTURE.md` changes its
sections as the chain changes, so a mention in a prompt, a comment or a document can go stale.
This reads where the pointers lead, never the prose around them.
"""

import re
from pathlib import Path

import pytest
from test_repo_text import ROOT, repository_files

ADR = ROOT / "docs" / "adr"
ARCHITECTURE = ROOT / "ARCHITECTURE.md"

_MARKDOWN_LINK = re.compile(r"\]\((?P<target>[^()\s]+)\)")
_ADR_PATH = re.compile(r"docs/adr/(?P<name>[0-9]{4}-[a-z0-9-]+\.md)")
_ADR_NUMBERS = re.compile(r"\bADRs? (?P<numbers>[0-9]{4}(?:(?:, | and )[0-9]{4})*)")
_SECTION = re.compile(r"ARCHITECTURE\.md, (?P<section>[A-Z][A-Za-z ]*[a-z])")
_HEADING = re.compile(r"#{1,6} (?P<title>.+)")
_FENCE = "```"


def slug(title: str) -> str:
    """Return the anchor GitHub gives a heading: lower case, no punctuation, hyphens for spaces."""
    kept = re.sub(r"[^\w\- ]", "", title.strip().lower())
    return kept.replace(" ", "-")


def headings(path: Path) -> list[str]:
    titles: list[str] = []
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(_FENCE):
            fenced = not fenced
        elif not fenced and (match := _HEADING.fullmatch(line)):
            titles.append(match["title"])
    return titles


def anchors(path: Path) -> set[str]:
    found: set[str] = set()
    seen: dict[str, int] = {}
    for title in headings(path):
        base = slug(title)
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def text_files() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in repository_files():
        try:
            found.append((path, path.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue  # binary, or a path git lists but the tree no longer holds
    return found


def record_numbers() -> set[str]:
    return {path.name[:4] for path in ADR.glob("[0-9][0-9][0-9][0-9]-*.md")}


def broken_links(path: Path, text: str) -> list[str]:
    """Markdown links to a record or to `ARCHITECTURE.md` whose file or anchor is missing."""
    broken: list[str] = []
    for match in _MARKDOWN_LINK.finditer(text):
        target, _, anchor = match["target"].partition("#")
        if not target or "://" in target:
            continue
        resolved = (path.parent / target).resolve()
        if resolved != ARCHITECTURE and resolved.parent != ADR:
            continue
        if not resolved.is_file() or (anchor and anchor not in anchors(resolved)):
            broken.append(match["target"])
    return broken


def test_the_architecture_has_sections() -> None:
    assert {"invariants", "codemap", "crosscutting-concerns"} <= anchors(ARCHITECTURE)


def test_every_link_to_a_record_or_to_the_architecture_resolves() -> None:
    broken = {
        str(path.relative_to(ROOT)): links
        for path, text in text_files()
        if path.suffix == ".md" and (links := broken_links(path, text))
    }
    assert not broken


def test_every_path_of_a_record_names_a_file_that_exists() -> None:
    missing = {
        (str(path.relative_to(ROOT)), match["name"])
        for path, text in text_files()
        for match in _ADR_PATH.finditer(text)
        if not (ADR / match["name"]).is_file()
    }
    assert not missing


def test_every_record_number_mentioned_exists() -> None:
    known = record_numbers()
    missing = {
        (str(path.relative_to(ROOT)), number)
        for path, text in text_files()
        for match in _ADR_NUMBERS.finditer(text)
        for number in re.findall(r"[0-9]{4}", match["numbers"])
        if number not in known
    }
    assert not missing


def test_every_section_of_the_architecture_mentioned_exists() -> None:
    titles = set(headings(ARCHITECTURE))
    missing = {
        (str(path.relative_to(ROOT)), match["section"])
        for path, text in text_files()
        for match in _SECTION.finditer(text)
        if match["section"] not in titles
    }
    assert not missing


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Invariants", "invariants"),
        ("Models left to the developer", "models-left-to-the-developer"),
        ("The `gates` block, again", "the-gates-block-again"),
    ],
)
def test_slug_follows_the_anchors_github_gives(title: str, expected: str) -> None:
    assert slug(title) == expected


def test_a_link_to_a_missing_anchor_or_record_is_found(tmp_path: Path) -> None:
    gone = "docs/adr/" + "9999-gone.md"  # split, so this file names no missing record
    text = (
        "[a](ARCHITECTURE.md#invariants) [b](ARCHITECTURE.md#nowhere)"
        f" [c](docs/adr/README.md) [d]({gone}) [e](https://example.com/x.md)"
    )
    assert broken_links(ROOT / "doc.md", text) == ["ARCHITECTURE.md#nowhere", gone]
    assert broken_links(tmp_path / "elsewhere.md", "[x](ARCHITECTURE.md)") == []
