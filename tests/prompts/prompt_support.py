"""Shared readers of the prompt tests: agents, skills, frontmatter, sections, script calls."""

import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents"
SKILLS = ROOT / "skills"

# The four agent roles, each with its key in the `models` setting.
ROLES = {
    "surface-extractor": "extractor",
    "surface-checker": "checker",
    "surface-executor": "executor",
    "surface-reviewer": "reviewer",
}
# The agent built into Claude Code that drafts the plan: the chain ships no definition for it, only
# its key in the `models` setting.
BUILT_IN_ROLES = {"Plan": "planner"}

_FENCE = "---\n"
_FIELD = re.compile(r"(?P<key>[A-Za-z][A-Za-z-]*): (?P<value>\S.*)")
# A call spelled `surface-status ...`, or by its path as a skill injects it at load, where
# `|| true` keeps a refusal from aborting the skill.
_CALL = re.compile(r"`(?:[^`\s]*/)?(surface-status [^`]+?)(?: \|\| true)?`")
_PLACEHOLDER = re.compile(r"<(?P<name>[^<>]+)>")


class FrontmatterError(ValueError):
    """An agent file whose frontmatter is not the flat `key: value` block the tests expect."""


def agent_file(name: str) -> Path:
    return AGENTS / f"{name}.md"


def split_agent(text: str) -> tuple[dict[str, str], str]:
    """Return the frontmatter fields and the body of an agent file.

    The frontmatter is kept to one `key: value` per line, so a reader never needs YAML.
    """
    if not text.startswith(_FENCE):
        message = "the file does not open with a frontmatter fence"
        raise FrontmatterError(message)
    head, fence, body = text[len(_FENCE) :].partition("\n" + _FENCE)
    if not fence:
        message = "the frontmatter is not closed"
        raise FrontmatterError(message)
    fields: dict[str, str] = {}
    for line in head.splitlines():
        match = _FIELD.fullmatch(line)
        if match is None:
            message = f"not a flat `key: value` line: {line!r}"
            raise FrontmatterError(message)
        if match["key"] in fields:
            message = f"duplicated key {match['key']!r}"
            raise FrontmatterError(message)
        fields[match["key"]] = match["value"].strip()
    return fields, body


def read_agent(name: str) -> tuple[dict[str, str], str]:
    return split_agent(agent_file(name).read_text(encoding="utf-8"))


def skill_file(name: str) -> Path:
    return SKILLS / name / "SKILL.md"


def read_skill(name: str) -> tuple[dict[str, str], str]:
    """Return the frontmatter fields and the body of a skill, read like an agent file."""
    return split_agent(skill_file(name).read_text(encoding="utf-8"))


def section(body: str, heading: str) -> str:
    """Return the text under a `## heading`, up to the next heading of the same level."""
    marker = f"\n## {heading}\n"
    start = body.find(marker)
    if start < 0:
        message = f"no section {heading!r}"
        raise LookupError(message)
    rest = body[start + len(marker) :]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def marked_block(text: str, mark: str) -> str:
    """Return the text between `<!-- mark -->` and `<!-- /mark -->`."""
    match = re.search(rf"<!-- {mark} -->\n(?P<block>.*?)\n<!-- /{mark} -->", text, re.DOTALL)
    if match is None:
        message = f"no block {mark!r}"
        raise LookupError(message)
    return match["block"]


def script_calls(body: str) -> list[str]:
    """Return every call of the state script a prompt spells in code, like `surface-status show`."""
    return [call for call in _CALL.findall(body) if len(shlex.split(call)) > 1]


def call_arguments(call: str) -> list[str]:
    """Turn a spelled call into arguments the parser can read, placeholders given sample values."""

    def sample(match: re.Match[str]) -> str:
        name = match["name"]
        if name == "plan":
            return "docs/plans/2024-01-15-sample"
        if name in {"n", "slice", "k"}:
            return "1"
        return "one-line-of-text"

    return shlex.split(_PLACEHOLDER.sub(sample, call))[1:]


def prompt_files() -> list[Path]:
    """Every prompt of the chain: the agents, and the skills once they exist."""
    return sorted(AGENTS.glob("surface-*.md")) + sorted(SKILLS.glob("surface-*/SKILL.md"))


def prompt_calls() -> list[tuple[str, str]]:
    """Every call of the state script the prompts spell, with the name of the prompt."""
    calls: list[tuple[str, str]] = []
    for path in prompt_files():
        name = path.parent.name if path.name == "SKILL.md" else path.stem
        calls.extend((name, call) for call in script_calls(path.read_text(encoding="utf-8")))
    return calls
