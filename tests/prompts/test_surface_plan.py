"""The `surface-plan` command and its templates (ADRs 0023, 0026 and 0031).

Prompt behavior is judged end to end. These tests hold what can be read: the frontmatter against
the fields the Claude Code documentation of skills defines, the state injected at load, the
planning sequence and the states this command resumes, the sensitive zones it carries, and
templates the script and the agents can read.
"""

import re
from fnmatch import fnmatchcase
from pathlib import Path

import pytest
from chain_contract import OVERVIEW_SECTIONS, PLAN, PLANNING_EVENTS, SEEN_BY
from prompt_support import (
    AGENTS,
    ROLES,
    SKILLS,
    call_arguments,
    read_skill,
    script_calls,
    section,
    skill_file,
)
from test_host_neutrality import denied_terms

from surface_status.machine import NON_TERMINAL
from surface_status.plan_folder import parse_slice_markers
from surface_status.settings import Models

SKILL = "surface-plan"
TEMPLATES = SKILLS / SKILL / "templates"
# Injected at load by its absolute path; called from the root of the repository by its relative
# path, the one a rule of the project settings can name.
SCRIPT = "${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status"
RELATIVE = ".claude/skills/surface-status/scripts/surface-status"

# Every frontmatter field of a skill the documentation lists; Claude Code ignores any other
# without a word, so a misspelled field would silently do nothing.
DOCUMENTED_FIELDS = {
    "name",
    "description",
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
    "metadata",
    "license",
    "compatibility",
}
# A plain YAML scalar must not open with an indicator, nor hold ": " or " #", or the frontmatter
# stops parsing and the skill loads with no field set.
_YAML_INDICATORS = tuple("[]{}!&*|>'\"%@`,?:-#")

_INJECTED = re.compile(r"^!`(?P<command>[^`]+)`$", re.MULTILINE)
_BASH_RULE = re.compile(r"Bash\((?P<pattern>[^()]+)\)")
_STATE_ROW = re.compile(r"^\| (?P<states>[^|]+) \| (?P<action>[^|]+) \|$", re.MULTILINE)
_STATE = re.compile(r"`(?P<state>[a-z]+(?:-[a-z]+)*)`")
_HEADING = re.compile(r"^## (?P<heading>.+)$", re.MULTILINE)


def _skill() -> tuple[dict[str, str], str]:
    return read_skill(SKILL)


def _body() -> str:
    return _skill()[1]


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _headings(text: str) -> list[str]:
    return [match["heading"] for match in _HEADING.finditer(text)]


def _positions(text: str, needles: list[str]) -> list[int]:
    positions = [text.find(needle) for needle in needles]
    missing = [needle for needle, at in zip(needles, positions, strict=True) if at < 0]
    assert not missing, f"not found: {missing}"
    return positions


def _allowed_patterns() -> list[str]:
    frontmatter, _ = _skill()
    return [match["pattern"] for match in _BASH_RULE.finditer(frontmatter["allowed-tools"])]


def _permitted(command: str) -> bool:
    """Whether a rule of `allowed-tools` matches, the way Bash rules match: `*` is any text."""
    return any(fnmatchcase(command, pattern) for pattern in _allowed_patterns())


# Frontmatter (ADRs 0023 and 0031).


def test_frontmatter_holds_only_documented_fields() -> None:
    frontmatter, _ = _skill()
    assert set(frontmatter) <= DOCUMENTED_FIELDS
    assert frontmatter["name"] == skill_file(SKILL).parent.name
    assert len(frontmatter["description"].split()) >= 8
    for key, value in frontmatter.items():
        assert not value.startswith(_YAML_INDICATORS), key
        assert ": " not in value, key
        assert " #" not in value, key


def test_only_the_developer_starts_the_command() -> None:
    frontmatter, _ = _skill()
    assert frontmatter["disable-model-invocation"] == "true"


def test_the_session_keeps_the_model_and_effort_the_developer_chose() -> None:
    frontmatter, body = _skill()
    assert "model" not in frontmatter
    assert "effort" not in frontmatter
    assert "${CLAUDE_EFFORT}" not in body
    assert "/model" not in body
    assert "/effort" not in body


def test_allowed_tools_grant_the_state_script_and_nothing_wider() -> None:
    assert sorted(_allowed_patterns()) == sorted([f"{SCRIPT} *", f"{RELATIVE} *", "true"])


# The state, read from the script at load.


def test_the_state_is_injected_at_load_and_a_refusal_does_not_abort() -> None:
    commands = [match["command"] for match in _INJECTED.finditer(_body())]
    assert commands == [f"{SCRIPT} resolve --for plan --json || true"]
    for command in commands:
        # Each part of `a || true` is checked alone; one the rules do not allow aborts the skill.
        assert all(_permitted(part) for part in command.split(" || "))


def test_injected_calls_parse_like_the_calls_in_prose() -> None:
    injected = [match["command"] for match in _INJECTED.finditer(_body())]
    spelled = script_calls("\n".join(f"`{command}`" for command in injected))
    assert [call_arguments(call) for call in spelled] == [["resolve", "--for", "plan", "--json"]]


def test_every_script_call_of_the_skill_is_permitted() -> None:
    for call in script_calls(_body()):
        assert _permitted(call.replace("surface-status", RELATIVE, 1)), call


def test_the_skill_calls_every_event_of_its_part() -> None:
    called = {tuple(call_arguments(call)[:3]) for call in script_calls(_body())}
    events = {arguments[2] for arguments in called if arguments[0] == "record"}
    assert events == {
        "plan-opened",
        "interview-closed",
        "check-done",
        "plan-drafted",
        "amendment-received",
        "plan-change-accepted",
        "plan-change-refused",
        "resumed",
        "blocked",
    }
    subcommands = {arguments[0] for arguments in called}
    assert subcommands == {"resolve", "show", "record", "pr-body"}


# Every resumption starts from the files, never from the conversation.


def test_resumption_reads_the_files_never_the_conversation() -> None:
    body = _body()
    resuming = section(body, "Resuming from files")
    assert "never from a conversation" in resuming
    assert "as soon as it is given, before anything else" in resuming
    assert "never from memory" in resuming
    assert "does not explore again" in resuming
    table = section(body, "Which plan")
    assert "the first question of `interview.md` without an answer" in table
    assert "Never ask again a question that has an answer" in table


def test_an_amendment_is_written_before_it_is_recorded() -> None:
    taking = section(_body(), "Taking an amendment")
    written, recorded, revised = _positions(
        taking, ["into `interview.md`", "amendment-received", "step 6"]
    )
    assert written < recorded < revised


def test_a_decision_on_a_proposal_is_written_before_it_is_recorded() -> None:
    proposal = section(_body(), "A plan change proposal")
    for event in ("plan-change-accepted", "plan-change-refused"):
        line = next(line for line in proposal.splitlines() if event in line)
        assert line.index("into `interview.md`") < line.index(event)


def test_a_launch_that_died_before_opening_its_plan_is_continued() -> None:
    which = section(_body(), "Which plan")
    assert "holding `specs.md` and no `journal.jsonl`" in which
    assert "continue at step 3" in which


# The planning sequence.


def test_first_launch_follows_the_planning_sequence() -> None:
    steps = section(_body(), "First launch, with specs")
    order = [
        "plan-opened",
        "`exploration.md`",
        "`interview.md`",
        "interview-closed",
        "`plan.md`",
        "`surface-extractor`",
        "`surface-checker`",
        "check-done",
        "plan-drafted",
        '"Commit, push and pull request"',
        "Tell the developer where to read the overview",
    ]
    assert [step for step in order if step in PLANNING_EVENTS] == list(PLANNING_EVENTS)
    positions = _positions(steps, order)
    assert positions == sorted(positions)


def test_questions_come_one_at_a_time_with_options_and_a_recommendation() -> None:
    asking = section(_body(), "Asking a question")
    assert "One question at a time, and wait for its answer before the next" in asking
    assert "names its options" in asking
    assert "the one you would pick with its reason" in asking
    assert "Never invent a business rule to fill a gap" in asking


def test_extraction_and_cross_check_go_to_fresh_agents_on_the_models_of_the_settings() -> None:
    agents = section(_body(), "The agents")
    assert "A fresh agent for each extraction and each cross-check" in agents
    assert "`model` its value in `settings.models`" in agents
    assert "file paths only, never the conversation" in agents
    for role in ("surface-extractor", "surface-checker"):
        assert f"`{role}`" in agents
        assert (AGENTS / f"{role}.md").is_file()
        assert f"`{ROLES[role]}`" in agents
        assert hasattr(Models(), ROLES[role])


def test_planning_stops_at_the_ceiling_and_hands_back() -> None:
    agents = section(_body(), "The agents")
    assert "passes.planning" in section(_body(), "First launch, with specs")
    assert "with the code `ceiling`" in agents
    assert "launch nothing more" in agents
    assert "record <plan> blocked --why" in agents


# The states this command resumes, and those it leaves to `/surface-execute`.


def _skill_table() -> dict[str, str]:
    table = section(_body(), "Which plan")
    actions: dict[str, str] = {}
    for row in _STATE_ROW.finditer(table):
        for state in _STATE.findall(row["states"]):
            actions[state] = row["action"]
    return actions


def test_the_resume_table_covers_every_state_in_progress() -> None:
    assert set(SEEN_BY) == {state.value for state in NON_TERMINAL}
    actions = _skill_table()
    assert set(SEEN_BY) <= set(actions)
    for state, commands in SEEN_BY.items():
        unseen = PLAN not in commands
        assert ("does not see this plan" in actions[state]) is unseen, state
    assert "first question of `interview.md` without an answer" in actions["interview"]
    assert "missing step" in actions["drafting"]
    assert '"Taking an amendment"' in actions["awaiting-approval"]
    assert '"A plan change proposal"' in actions["plan-change-proposed"]
    assert '"After a block"' in actions["blocked"]


def test_the_terminal_states_are_said_over() -> None:
    actions = _skill_table()
    assert "The plan is over" in actions["conform"]
    assert "The plan is over" in actions["abandoned"]


def test_a_block_is_taken_back_by_planning_or_by_amendment() -> None:
    block = section(_body(), "After a block")
    assert "no `plan-approved` after its last" in block
    planning, execution = (line for line in block.splitlines() if line.startswith("- During"))
    assert 'under "Instructions after a block"' in planning
    assert "record <plan> resumed" in planning
    assert "take the amendment" in execution
    assert "`/surface-execute` resumes it" in execution


# The sensitive zones this command carries.


def test_a_new_branch_only_from_the_main_branch() -> None:
    steps = section(_body(), "First launch, with specs")
    branch = next(line for line in steps.splitlines() if line.startswith("2. Branch."))
    # The order ADR 0015 gives the script, so the command and the script agree on "main".
    assert "`origin/HEAD`, else `main`, else `master`" in branch
    assert "Launched from the main branch, create a branch" in branch
    assert "From any other branch, stay" in branch
    assert "A new branch comes only from the main branch" in branch


def test_an_amendment_outside_the_hand_is_explained_and_refused() -> None:
    body = _body()
    outside = section(body, "Outside your hand")
    assert "only when they have the hand: awaiting approval, or blocked" in outside
    for state in ("executing", "reviewing", "fixing"):
        assert f"`{state}`" in outside
    assert "record nothing" in outside
    assert "wait for the loop to stop" in outside
    assert "abandon the plan with `/surface-status`" in outside
    assert section(body, "Taking an amendment").startswith(
        "\nOnly in `awaiting-approval`, or `blocked` during execution."
    )


def test_the_overview_template_holds_the_nine_sections_and_no_slice() -> None:
    template = _template("overview.md")
    headings = _headings(template)
    assert headings == list(OVERVIEW_SECTIONS)
    _, extractor = (AGENTS / "surface-extractor.md").read_text(encoding="utf-8").split("\n---\n", 1)
    for heading in headings:
        assert heading in extractor
        assert "slice" not in heading.lower()
    assert template.count("No change.") == 9
    assert parse_slice_markers(template) == ()


# Git, pull request and CI.


def _git_steps() -> list[str]:
    part = section(_body(), "Commit, push and pull request")
    return [line for line in part.splitlines() if line.startswith("- ")]


def test_the_ci_triggers_are_read_before_the_first_push() -> None:
    steps = _git_steps()
    check = next(i for i, step in enumerate(steps) if step.startswith("- Before the first push"))
    push = next(i for i, step in enumerate(steps) if step.startswith("- Push the branch"))
    assert check < push
    warning = steps[check]
    assert "read the CI configuration" in warning
    assert "react to a push of this branch or to the opening of a pull request" in warning
    assert "wait for their agreement" in warning
    assert 'under "Git", so a relaunch does not ask again' in warning


def test_the_draft_pull_request_opens_at_the_first_plan_drafted() -> None:
    body = _body()
    steps = "\n".join(_git_steps())
    assert "opens as a draft at the first `plan-drafted`" in steps
    assert "`gh pr create --draft`" in steps
    assert "`surface-status pr-body` prints, and nothing else" in steps
    assert "Nothing else is written on the pull request" in steps
    assert "never mark it ready for review" in steps
    assert "read only when the developer asks for it explicitly" in steps
    drafted, pushed = _positions(body, ["record <plan> plan-drafted", "Push the branch"])
    assert drafted < pushed


def test_commits_hold_only_the_plan_folder_with_its_journal_lines() -> None:
    commit = _git_steps()[0]
    assert "only the files of the plan folder, by path" in commit
    assert "Each journal line goes in the commit of the files it describes" in commit


# Boundaries: this command writes neither code, nor the overview, nor the journal.


def test_the_command_writes_only_in_the_plan_folder() -> None:
    opening = _body().split("\n## ", 1)[0]
    assert "You write only in the plan folder" in opening
    assert "never the code, never `overview.md`" in opening
    assert "never `journal.jsonl` (the state script alone writes it)" in opening


# Templates (ADR 0026).


@pytest.mark.parametrize("name", ["plan.md", "overview.md", "interview.md", "exploration.md"])
def test_every_template_is_cited_and_follows_the_language_of_the_specs(name: str) -> None:
    assert f"${{CLAUDE_SKILL_DIR}}/templates/{name}" in _body()
    assert "Written in the language of `specs.md`" in _template(name)


def test_the_extractor_is_given_the_overview_template() -> None:
    assert "`${CLAUDE_SKILL_DIR}/templates/overview.md`" in section(_body(), "The agents")


def test_the_cited_templates_exist() -> None:
    cited = re.findall(r"\$\{CLAUDE_SKILL_DIR\}/(templates/[\w.-]+)", _body())
    assert cited
    for path in cited:
        assert (SKILLS / SKILL / path).is_file(), path


def test_the_plan_template_has_the_sections_of_the_specs_and_readable_markers() -> None:
    template = _template("plan.md")
    assert _headings(template) == [
        "1. Goal and scope",
        "2. Architecture decisions",
        "3. Slices",
        "4. Tests",
        "5. Definition of Done",
        "6. Risks and assumptions",
    ]
    assert parse_slice_markers(template) == (1,)


def test_the_interview_template_holds_every_heading_the_skill_writes_under() -> None:
    headings = set(_headings(_template("interview.md")))
    lines = [line for line in _body().splitlines() if "`interview.md`" in line]
    under = set(re.findall(r'under "([^"]+)"', "\n".join(lines)))
    assert under
    assert under <= headings
    assert "Answer (<date>)" in _template("interview.md")


@pytest.mark.parametrize("path", sorted(TEMPLATES.glob("*.md")), ids=lambda path: path.name)
def test_templates_name_no_host_and_assume_no_stack(path: Path) -> None:
    assert denied_terms(path.read_text(encoding="utf-8")) == set()


def test_the_skill_stays_under_the_documented_size() -> None:
    assert len(skill_file(SKILL).read_text(encoding="utf-8").splitlines()) < 500
