#!/usr/bin/env python3
"""Commit message hook: refuse an em dash and any attribution to Claude.

Claude as an author or a tool is refused: attribution trailers, "generated with"
lines, links to Claude or Anthropic, and Claude as a standalone word of the prose.
Paths and identifiers that merely contain the name are accepted: `.claude/`,
`CLAUDE.md`, `${CLAUDE_PROJECT_DIR}`, and anything inside backticks.
"""

import re
import sys
from pathlib import Path

EM_DASH = chr(0x2014)  # a code point, so this file holds no literal em dash
SCISSORS = "# ------------------------ >8 ------------------------"
CODE_SPAN = re.compile(r"`[^`\n]*`")
# The name alone, not a piece of a path or an identifier: nothing of `.claude/`,
# `CLAUDE.md` or `CLAUDE_PROJECT_DIR` may touch it. A hyphen does not protect it,
# so "Claude-generated" and "Claude-Session:" are words of the prose.
STANDALONE = re.compile(r"(?<![\w./${])claude(?!\w|\.\w)", re.IGNORECASE)
ATTRIBUTION_TRAILER = re.compile(
    r"^[ \t]*[A-Za-z][\w-]*-by[ \t]*:.*(claude|anthropic)", re.IGNORECASE | re.MULTILINE
)
GENERATED_WITH = re.compile(
    r"\b(generated|written|created|authored|assisted|made|produced)\s+(with|by|using)"
    r"\s+[\[`\"'(]?claude(?!\w|\.\w)",
    re.IGNORECASE,
)
LINK = re.compile(r"\b(claude\.(ai|com)|anthropic\.com)\b", re.IGNORECASE)
EXPECTED_ARGV_LENGTH = 2  # program name and message file


def committed_text(message: str) -> str:
    """Keep what git commits by default: no comment line, nothing below the scissors."""
    kept = message.split(SCISSORS, 1)[0]
    return "\n".join(line for line in kept.splitlines() if not line.startswith("#"))


def violations(message: str) -> list[str]:
    text = committed_text(message)
    found: list[str] = []
    if EM_DASH in text:
        found.append("the message contains an em dash")
    if ATTRIBUTION_TRAILER.search(text) or GENERATED_WITH.search(text):
        found.append("the message attributes the work to Claude")
    if LINK.search(text):
        found.append("the message links to Claude or Anthropic")
    if STANDALONE.search(CODE_SPAN.sub("", text)):
        found.append(
            "the message mentions Claude as a word"
            " (paths such as .claude/ or CLAUDE.md are fine, commands go in backticks)"
        )
    return found


def main(argv: list[str]) -> int:
    if len(argv) != EXPECTED_ARGV_LENGTH:
        sys.stderr.write("usage: check_commit_msg.py <message-file>\n")
        return 2
    problems = violations(Path(argv[1]).read_text(encoding="utf-8"))
    for problem in problems:
        sys.stderr.write(f"commit refused: {problem}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
