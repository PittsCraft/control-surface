"""The frontmatter of the four agent definitions (ADR 0031, and ARCHITECTURE.md, Invariants).

Fields and their meaning follow the Claude Code documentation of subagents: `name` and
`description` are required, `tools` narrows what the agent inherits, `model` takes an alias and
is overridden by the `model` of each Agent call, `effort` exists in the frontmatter only.
"""

from dataclasses import fields

import pytest
from prompt_support import AGENTS, ROLES, FrontmatterError, read_agent, split_agent

from surface_status.settings import Models

# Model aliases the documentation lists; a full model identifier would stop following releases.
MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable"}
# Effort per role: high for the three judgment roles, the default otherwise.
EFFORT = {"extractor": "high", "checker": "high", "reviewer": "high", "executor": None}
# Tools a role may hold: each is a leaf, so neither `Agent` nor its old name `Task`.
KNOWN_TOOLS = {"Read", "Glob", "Grep", "Edit", "Write", "Bash"}
SPAWNING_TOOLS = {"Agent", "Task"}


def test_the_agent_directory_holds_the_four_roles() -> None:
    assert sorted(path.stem for path in AGENTS.glob("*.md")) == sorted(ROLES)


def test_every_role_has_a_setting_and_every_setting_a_role() -> None:
    assert sorted(ROLES.values()) == sorted(f.name for f in fields(Models))


@pytest.mark.parametrize("name", sorted(ROLES))
def test_frontmatter_holds_the_expected_fields_and_no_other(name: str) -> None:
    frontmatter, _ = read_agent(name)
    expected = {"name", "description", "tools", "model"}
    if EFFORT[ROLES[name]] is not None:
        expected.add("effort")
    # Nothing else: no isolation, no permission mode, no background.
    assert set(frontmatter) == expected


@pytest.mark.parametrize("name", sorted(ROLES))
def test_name_equals_the_file_name(name: str) -> None:
    frontmatter, _ = read_agent(name)
    assert frontmatter["name"] == name


@pytest.mark.parametrize("name", sorted(ROLES))
def test_description_is_present(name: str) -> None:
    frontmatter, _ = read_agent(name)
    assert len(frontmatter["description"].split()) >= 8


@pytest.mark.parametrize("name", sorted(ROLES))
def test_model_is_an_alias_and_the_default_of_the_settings(name: str) -> None:
    frontmatter, _ = read_agent(name)
    assert frontmatter["model"] in MODEL_ALIASES
    # The command passes the model of `surface.json` on each call; the frontmatter only holds
    # the same default, so a definition launched without it runs on the documented model.
    assert frontmatter["model"] == getattr(Models(), ROLES[name])


@pytest.mark.parametrize("name", sorted(ROLES))
def test_effort_per_role(name: str) -> None:
    frontmatter, _ = read_agent(name)
    assert frontmatter.get("effort") == EFFORT[ROLES[name]]


@pytest.mark.parametrize("name", sorted(ROLES))
def test_tools_are_listed_and_hold_no_agent_tool(name: str) -> None:
    frontmatter, _ = read_agent(name)
    # Listed, never omitted: an agent without `tools` inherits every tool, `Agent` included.
    tools = {tool.strip() for tool in frontmatter["tools"].split(",")}
    assert not tools & SPAWNING_TOOLS
    assert tools <= KNOWN_TOOLS


def test_the_reviewer_and_the_checker_cannot_edit() -> None:
    for name in ("surface-reviewer", "surface-checker"):
        frontmatter, _ = read_agent(name)
        assert "Edit" not in frontmatter["tools"]


@pytest.mark.parametrize(
    "text",
    [
        "name: x\n---\nbody",
        "---\nname: x\nbody",
        "---\nname: x\nname: y\n---\n",
        "---\ntools:\n  - Read\n---\n",
    ],
)
def test_the_reader_refuses_a_frontmatter_it_cannot_read_flat(text: str) -> None:
    with pytest.raises(FrontmatterError):
        split_agent(text)
