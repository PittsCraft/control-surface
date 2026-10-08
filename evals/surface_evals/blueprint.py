"""The form of a blueprint, read from its text: the frame, the cut of the body, the diagrams.

The frame is the one the extractor is held to: three opening sections and a closing one, with no
number on a heading. What stands between them is the body, cut for the feature. A test holds
these headings equal to those of the template the extractor is given.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

OPENING = ("The idea in one sentence", "Acceptance criteria", "Scope and out of scope")
CLOSING = "Sensitive zones"
CLOSING_LINE = "No change:"
# The words the closing section opens on, the head of the lead-in the template gives: the
# statement of the critical zones follows them, after a colon. A test holds them to the template.
LEAD_IN = "Critical zones touched"
# What that statement says when the plan touches none, and what it holds between backticks.
_NONE = re.compile(r"\W*none\b", re.IGNORECASE)
_SPAN = re.compile(r"`[^`\n]+`")
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
# Outside the form, how a blueprint says the plan touches no critical zone: none, or neither of
# two.
NONE_TOUCHED = re.compile(r"\b(none|neither|no critical zone)\b", re.IGNORECASE)
# The same said outright, of the zones and of nothing else: "Critical zones touched: none",
# "None is touched", "the plan touches neither of the two critical zones".
_NONE_OUTRIGHT = re.compile(
    r"\bno critical zone\b"
    r"|\bzones? touched[^:\n]*:\s*none\b(?!\s+of\b)"
    r"|\bnone (?:is|are) touched\b"
    r"|\btouch(?:es|ed)? (?:none|neither)\b"
    r"(?:\s*[.,;:)]|\s*$|\s+(?:critical )?zones?\b"
    r"|\s+of (?:the|these|those)(?: \w+){0,2}? (?:critical )?zones?\b)",
    re.IGNORECASE,
)

_HEADING = re.compile(r"## (?P<title>.+)")
_FENCE = re.compile(r"```(?P<tag>\S*)")
_NUMBERED = re.compile(r"[0-9]+[.)]? ")
_CRITERION = re.compile(r"[0-9]+\. ")
# A title inside a section: a few words in bold at the head of a paragraph, as a developer looks
# for one, "**The name of the file.** It carries the day". An item of a list is not one.
_TITLE = re.compile(r"\*\*[^*\n]+\*\*")
# What a paragraph is not: a table, a block of code indented or fenced.
_NOT_PROSE = ("|", "    ", "\t", "```")
# A section the developer takes in at a glance holds no more paragraphs than this.
GLANCE = 2


@dataclass(frozen=True, slots=True)
class Section:
    title: str
    text: str
    diagrams: int

    @property
    def paragraphs(self) -> tuple[str, ...]:
        """Its paragraphs and its lists, which blank lines part, a fence left whole and out."""
        blocks: list[str] = []
        lines: list[str] = []
        fenced = False
        for line in (*self.text.splitlines(), ""):
            if _FENCE.fullmatch(line.strip()) is not None:
                fenced = not fenced
            if line.strip() or fenced:
                lines.append(line)
            elif lines:
                blocks.append("\n".join(lines))
                lines = []
        return tuple(block for block in blocks if not block.startswith(_NOT_PROSE))

    @property
    def inner_titles(self) -> int:
        """How many of its paragraphs open with a title in bold."""
        return sum(1 for block in self.paragraphs if _TITLE.match(block))

    @property
    def untitled_and_long(self) -> bool:
        """Whether it is longer than a glance and holds no title to find a rule by."""
        return len(self.paragraphs) > GLANCE and self.inner_titles == 0


@dataclass(frozen=True, slots=True)
class Blueprint:
    sections: tuple[Section, ...]

    @property
    def titles(self) -> tuple[str, ...]:
        return tuple(section.title for section in self.sections)

    @property
    def framed(self) -> bool:
        """Whether it opens and closes with the sections of the frame, around a body."""
        titles = self.titles
        return (
            len(titles) > len(OPENING) + 1
            and titles[: len(OPENING)] == OPENING
            and titles[-1] == CLOSING
        )

    @property
    def body(self) -> tuple[Section, ...]:
        """The sections between the frame, or all of them when the frame is not there."""
        return self.sections[len(OPENING) : -1] if self.framed else self.sections

    @property
    def numbered(self) -> tuple[str, ...]:
        return tuple(title for title in self.titles if _NUMBERED.match(title))

    @property
    def diagrams(self) -> int:
        return sum(section.diagrams for section in self.sections)

    @property
    def criteria(self) -> int:
        found = [section for section in self.sections if section.title == OPENING[1]]
        if not found:
            return 0
        return sum(1 for line in found[0].text.splitlines() if _CRITERION.match(line))

    @property
    def zones(self) -> str:
        """The text of the closing section, where the critical zones the plan touches are named."""
        found = [section for section in self.sections if section.title == CLOSING]
        return found[-1].text if found else ""

    @property
    def closing_line(self) -> str | None:
        """What the last line says the plan leaves alone, or None without one."""
        for line in reversed(self.zones.splitlines()):
            if line.startswith(CLOSING_LINE):
                return line[len(CLOSING_LINE) :].strip()
        return None

    @property
    def words(self) -> int:
        return sum(len(section.text.split()) for section in self.sections)


@dataclass(frozen=True, slots=True)
class Statement:
    """What a closing section states of the critical zones, in the sentence it opens on."""

    none: bool  # it says that the plan touches none
    files: tuple[str, ...]  # the files it announces, as written between backticks


def statement(zones: str, declared: Sequence[str]) -> Statement | None:
    """Read the sentence a closing section opens on, or None when it is outside the form.

    The form is the one the extractor is held to: the lead-in of the template, a colon, then
    `none`, or each zone the plan touches with in backticks its files the plan changes, to the
    end of the sentence. The colon and that end are looked for outside backticks, since a path
    holds a full stop. What stands between backticks there is a file the page announces, but
    for a word the host names a zone with, `loans.jsonl`, one of the phrases given. What
    follows the sentence says how far the plan goes, and names a file only to tell of it.

    A section that opens on other words is outside the form, and so is one whose lead-in ends
    its line, the zones in a list under it: no one sentence states them there.
    """
    opening = zones.lstrip().split("\n\n", 1)[0]
    if not opening.lower().startswith(LEAD_IN.lower()):
        return None
    # The same text with nothing to find between backticks, at the same places.
    bare = _SPAN.sub(lambda span: "`" * len(span[0]), opening)
    colon = bare.find(":")
    if colon < 0 or not bare[colon + 1 :].split("\n", 1)[0].strip():
        return None
    end = _SENTENCE_END.search(bare, colon + 1)
    said = opening[colon + 1 : len(opening) if end is None else end.start()].strip()
    names = {phrase.lower() for phrase in declared}
    files = (span[1:-1] for span in _SPAN.findall(said))
    return Statement(
        none=_NONE.match(said) is not None,
        files=tuple(file for file in files if file.lower() not in names),
    )


def says_none(zones: str, declared: Sequence[str]) -> bool:
    """Whether a closing section opens on the statement that the plan touches no critical zone.

    In the form, the sentence the section opens on says it: `none` after the lead-in, and no
    other wording. A page outside the form is read as free prose, by the paragraph it opens
    on: it says none when it says so outright, or by a "none" or a "neither" that comes before
    any zone the host declares, named by one of the phrases given. After a zone is named, such
    a word says how far the plan goes into it, "which changes none of its fields": the zone is
    touched. That reading guesses, and is kept for the pages drawn before the form.
    """
    stated = statement(zones, declared)
    if stated is not None:
        return stated.none
    opening = zones.split("\n\n", 1)[0].lower()
    if _NONE_OUTRIGHT.search(opening) is not None:
        return True
    said = NONE_TOUCHED.search(opening)
    if said is None:
        return False
    return not any(phrase.lower() in opening[: said.start()] for phrase in declared)


def parse(text: str) -> Blueprint:
    """Read the second level sections of a blueprint, a heading inside a fence left alone."""
    sections: list[Section] = []
    title: str | None = None
    lines: list[str] = []
    diagrams = 0
    fenced = False

    def close() -> None:
        if title is not None:
            sections.append(Section(title, "\n".join(lines).strip(), diagrams))

    for line in text.splitlines():
        fence = _FENCE.fullmatch(line.strip())
        heading = None if fenced else _HEADING.fullmatch(line)
        if heading is not None:
            close()
            title, lines, diagrams = heading["title"].strip(), [], 0
            continue
        if fence is not None:
            if not fenced and fence["tag"] == "mermaid":
                diagrams += 1
            fenced = not fenced
        lines.append(line)
    close()
    return Blueprint(tuple(sections))
