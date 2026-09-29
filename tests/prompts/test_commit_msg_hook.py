from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import check_commit_msg

EM_DASH = chr(0x2014)  # a code point, so this file holds no literal em dash

# Paths and identifiers that contain the name without naming an author or a tool.
TECHNICAL = [
    ".claude/",
    ".claude/skills/surface-plan",
    ".claude/agents/surface-reviewer.md",
    "CLAUDE.md",
    "claude.md",
    "${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status",
    "$CLAUDE_EFFORT",
    "CLAUDE_SKILL_DIR",
    "@anthropic-ai/claude-code",
    "`claude plugin validate agents --strict`",
    "`claude -p`",
]

# Words of a message that neither name Claude nor open an attribution trailer.
PROSE = st.text(
    alphabet=st.characters(codec="ascii", categories=["L", "N", "Zs", "P"]),
    max_size=40,
).filter(lambda text: all(marker not in text.lower() for marker in ("claude", "anthropic", "-by")))
WORDS = st.lists(st.one_of(PROSE, st.sampled_from(TECHNICAL)), max_size=12)


def message_of(words: list[str]) -> str:
    """Open on a subject line, since git drops a line that starts with a comment sign."""
    return " ".join(["Add the slice", *words])


@pytest.mark.parametrize(
    "message",
    [
        "Add the installer",
        "Fix drift check\n\nBody with a hyphen - and an en dash \u2013 is fine.",
        "Install the chain into .claude/ of its own repository",
        "Copy .claude/skills/surface-plan and .claude/agents/surface-*.md",
        "Mention CLAUDE.md in the README",
        "Call the script through ${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status",
        "Run `claude plugin validate skills` when the CLI is present",
        "Add the slice\n\n# Please enter the commit message.\n#\tmodified: notes by Claude",
        f"Add the slice\n{check_commit_msg.SCISSORS}\n+Co-Authored-By: Claude",
    ],
)
def test_clean_messages_pass(message: str) -> None:
    assert check_commit_msg.violations(message) == []


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        (f"Add the installer {EM_DASH} finally", "em dash"),
        ("Add the installer\n\nCo-Authored-By: Claude <noreply@anthropic.com>", "attributes"),
        ("Add it\n\nCo-authored-by: Assistant <noreply@anthropic.com>", "attributes"),
        ("Add it\n\nGenerated with [Claude Code](https://claude.com/claude-code)", "attributes"),
        ("Add it\n\nGenerated with `claude`", "attributes"),
        ("Add it\n\nClaude-Session: https://claude.ai/code/session_1", "links"),
        ("written with CLAUDE", "Claude as a word"),
        ("claude-session: abc", "Claude as a word"),
        ("Claude-generated fixture", "Claude as a word"),
        ("Ask Claude, then commit", "Claude as a word"),
        ("Claude's review of the diff", "Claude as a word"),
        ("A pass (Claude) on the plan", "Claude as a word"),
        ("Thanks to claude.", "Claude as a word"),
        ("Move files from claude/ to docs/", "Claude as a word"),
    ],
)
def test_faulty_messages_are_refused(message: str, reason: str) -> None:
    assert any(reason in problem for problem in check_commit_msg.violations(message))


@given(words=WORDS)
def test_prose_with_paths_and_identifiers_passes(words: list[str]) -> None:
    assert check_commit_msg.violations(message_of(words)) == []


@given(
    words=WORDS,
    position=st.integers(min_value=0),
    name=st.sampled_from(["claude", "Claude", "CLAUDE", "cLaUdE"]),
    before=st.sampled_from(["", "(", '"', "[", "'"]),
    after=st.sampled_from(["", ".", ",", ")", "'s", ":", "!", "-generated", " Code"]),
)
def test_claude_as_a_standalone_word_is_refused(
    words: list[str], position: int, name: str, before: str, after: str
) -> None:
    words.insert(position % (len(words) + 1), f"{before}{name}{after}")

    problems = check_commit_msg.violations(message_of(words))

    assert any("Claude as a word" in problem for problem in problems)


def test_main_exit_codes(tmp_path: Path) -> None:
    good = tmp_path / "good"
    good.write_text("Install into .claude/ and read CLAUDE.md\n", encoding="utf-8")
    bad = tmp_path / "bad"
    bad.write_text(f"Add a thing {EM_DASH} and Claude\n", encoding="utf-8")
    assert check_commit_msg.main(["hook", str(good)]) == 0
    assert check_commit_msg.main(["hook", str(bad)]) == 1
    assert check_commit_msg.main(["hook"]) == 2
