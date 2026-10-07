"""The form of a blueprint, read from its text: the frame, the cut of the body, the diagrams.

The frame is the one the extractor is held to: three opening sections and a closing one, with no
number on a heading. What stands between them is the body, cut for the feature. A test holds
these headings equal to those of the template the extractor is given.
"""

import re
from dataclasses import dataclass

OPENING = ("The idea in one sentence", "Acceptance criteria", "Scope and out of scope")
CLOSING = "Sensitive zones"
CLOSING_LINE = "No change:"
# How a blueprint says the plan touches no critical zone: none, or neither of two.
NONE_TOUCHED = re.compile(r"\b(none|neither|no critical zone)\b", re.IGNORECASE)

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
