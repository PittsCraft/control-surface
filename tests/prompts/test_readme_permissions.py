"""The permissions an unattended loop needs, in the README's developer path (ADRs 0028, 0030).

The block must parse as settings, grant what the commands grant themselves for one turn only, and
name the state script by the path the prompts call it with. What an agent runs to explore is left
to the permission mode: the section warns that the loop stops at each command not allowed.
"""

import json
import re
from typing import Any

from prompt_support import ROOT, read_skill

SCRIPT = ".claude/skills/surface-status/scripts/surface-status"
_RULE = re.compile(r"Bash\([^()]*\)")


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _path_section() -> str:
    """Return the developer's path: from its heading to the next heading of the same level."""
    text = _readme()
    start = text.index("\n## Your path")
    return text[start : text.index("\n## ", start + 1)]


def _permissions() -> str:
    path = _path_section()
    start = path.index("\n### Permissions\n")
    return path[start : path.index("\n### ", start + 1)]


def _allowed() -> list[str]:
    block = _permissions().split("```json\n", 1)[1].split("```", 1)[0]
    settings: dict[str, Any] = json.loads(block)
    rules: list[str] = settings["permissions"]["allow"]
    return rules


def test_the_permissions_come_before_the_agents_work() -> None:
    path = _path_section()
    assert path.index("### Permissions") < path.index("### 3. Let the agents work")


def test_the_block_grants_what_the_commands_grant_for_one_turn() -> None:
    allowed = set(_allowed())
    for name in ("surface-execute", "surface-status"):
        fields, _ = read_skill(name)
        assert set(_RULE.findall(fields["allowed-tools"])) <= allowed, name
    assert f"Bash({SCRIPT} *)" in allowed
    assert {"Bash(gh pr edit *)", "Bash(gh pr ready *)"} <= allowed


def test_the_block_names_the_gate_command_as_an_example() -> None:
    assert "The last rule is an example: name your gate command" in _permissions()


def test_the_section_warns_that_missing_permissions_stop_the_loop() -> None:
    section = _permissions()
    assert "> [!WARNING]" in section
    assert "The loop stops at every command your permission rules or mode do not allow" in section
    assert "auto mode (`claude --permission-mode auto`)" in section


def test_the_install_line_points_at_the_section() -> None:
    assert "[Permissions](#permissions)" in _readme()
