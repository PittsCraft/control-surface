"""The models the README recommends, in the developer's path (ADR 0031).

The session's model and effort are the developer's: the README says what to choose for planning,
and that the agents run on the models of `surface.json` whatever the session runs on.
"""

from prompt_support import ROOT


def _section(heading: str) -> str:
    """Return a step of the developer's path: from its heading to the next heading."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index(f"\n### {heading}\n")
    return text[start : text.index("\n#", start + 1)]


def test_the_readme_recommends_opus_with_high_effort_for_planning() -> None:
    plan = _section("1. Plan: `/surface-plan`")
    assert "It runs on your session's model and effort" in plan
    assert "Opus with the effort `high` is recommended" in plan
    assert "`/model opus`" in plan
    assert "`/effort high`" in plan


def test_the_readme_says_the_dispatch_holds_on_any_model() -> None:
    agents = _section("3. Let the agents work")
    assert "`/surface-execute` dispatches soundly on any model" in agents
    assert "The agents run on the models of `.claude/surface.json`" in agents


def test_the_readme_no_longer_speaks_of_later_turns_and_their_model() -> None:
    agents = _section("3. Let the agents work")
    assert "later turn" not in agents
    assert "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS" not in agents
