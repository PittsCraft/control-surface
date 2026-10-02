"""The `surface-plan` command and its templates (ADR 0031).

Prompt behavior is judged end to end. These tests hold what can be read: the frontmatter against
the fields the Claude Code documentation of skills defines, the state injected at load, the
planning sequence and the states this command resumes, the hand it keeps in the conversation, the
sensitive zones it carries, and templates the script and the agents can read.
"""

import re
from fnmatch import fnmatchcase
from pathlib import Path

import pytest
from chain_contract import (
    ALWAYS_WRITTEN,
    BLUEPRINT_SECTIONS,
    CLOSING_LINE,
    DOCUMENTS_LANGUAGE,
    FORMER_LANGUAGE_RULE,
    LANGUAGE_SOURCES,
    PLAN,
    PLANNING_EVENTS,
    SEEN_BY,
)
from prompt_support import (
    AGENTS,
    ROLES,
    SKILLS,
    call_arguments,
    prompt_files,
    read_skill,
    script_calls,
    section,
    skill_file,
)
from test_host_neutrality import denied_terms

from surface_status.machine import NON_TERMINAL
from surface_status.plan_folder import parse_gates, parse_slice_markers
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


# Frontmatter (ADR 0031).


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
    assert "a reply is written before it is acted on" in resuming
    assert "never by a sentence of the conversation" in resuming
    assert "After a dead session, relaunching `/surface-plan` is the way to resume" in resuming
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


def test_a_proposal_relaunched_here_is_taken_once() -> None:
    proposal = section(_body(), "A plan change proposal")
    assert "`/surface-execute` puts it to the developer itself" in proposal
    assert "already holds the decision on this proposal, take it and ask nothing again" in proposal


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
        # The step that creates it: the branch step names it earlier, for a question it holds.
        "in `interview.md` from",
        "interview-closed",
        "`plan.md`",
        "`surface-extractor`",
        "`surface-checker`",
        "check-done",
        "plan-drafted",
        '"Commit, push and pull request"',
        "Tell the developer where to read the blueprint",
    ]
    assert [step for step in order if step in PLANNING_EVENTS] == list(PLANNING_EVENTS)
    positions = _positions(steps, order)
    assert positions == sorted(positions)


def test_the_plan_folder_names_no_path_of_the_machine_and_passes_the_gates() -> None:
    steps = section(_body(), "First launch, with specs")
    assert "a path under a home directory becomes a neutral form such as `/path/to/...`" in steps
    assert "Tell the developer what you replaced" in steps
    assert "Every document you write in the plan folder must pass the gates of step 1" in steps


# Languages: the plan folder is the repository's, the conversation the developer's.


def test_the_documents_language_is_found_at_step_one_in_order() -> None:
    steps = section(_body(), "First launch, with specs")
    conventions = steps.split("\n2. Branch.", 1)[0]
    assert "The documents' language" in conventions
    assert "the first that answers wins" in conventions
    positions = _positions(conventions, list(LANGUAGE_SOURCES))
    assert positions == sorted(positions)


def test_the_documents_language_is_written_once_where_every_agent_reads_it() -> None:
    languages = section(_body(), "Languages")
    assert "written once in `exploration.md`, in its repository rules" in languages
    assert "every agent reads it there" in languages
    assert "The markers, the `gates` tag and the journal stay as they are" in languages


def test_the_conversation_stays_in_the_developers_language() -> None:
    languages = section(_body(), "Languages")
    assert "Speak to the developer in the language they write in" in languages
    assert "questions, options, hand-overs and summaries" in languages
    assert "not repository content" in languages


def test_the_developers_words_are_quoted_as_given_then_translated() -> None:
    body = _body()
    languages = section(body, "Languages")
    for quoted in ("`specs.md`", "answer", "amendment", "decision", "instruction"):
        assert quoted in languages
    assert "is quoted in their words, then" in languages
    assert "followed by its translation into the documents' language" in languages
    assert "Everything you write yourself is in the documents' language only" in languages
    assert "the original is the reference when the two disagree" in languages
    steps = section(body, "First launch, with specs")
    assert "add their translation below the text, under a heading that says so" in steps
    for writing in (section(body, "Asking a question"), section(body, "Taking an amendment")):
        assert 'in the developer\'s words then translated (see "Languages")' in writing


def test_the_interview_template_quotes_then_translates() -> None:
    template = _template("interview.md")
    assert "The developer's words are quoted as given, then translated" in template
    assert "Answer (<date>): <the developer's words, as given>" in template
    assert "<their translation, when they are in another language>" in template


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


def test_planning_stops_at_the_ceiling_and_asks_in_the_conversation() -> None:
    agents = section(_body(), "The agents")
    first = section(_body(), "First launch, with specs")
    # The script records the check past the ceiling, which hands back: the ceiling is passed.
    assert "`passes.planning` of `show` is more than `passes.ceiling`" in first
    assert "A pass is a cross-check with omissions" in first
    assert "`passes.planning` is more than `passes.ceiling`" in agents
    assert "with the code `ceiling`" in agents
    assert "launch nothing more" in agents
    ceiling = next(line for line in agents.splitlines() if line.startswith("Stop at the ceiling"))
    positions = _positions(
        ceiling,
        [
            "record <plan> blocked --why",
            "keep the hand: present what does not converge",
            "ask the developer's instruction in the conversation",
            '"After a block"',
        ],
    )
    assert positions == sorted(positions)
    assert "`/surface-plan`" not in ceiling


# The hand-over: the command keeps the hand, and only the launch of `/surface-execute` approves.


def _hand_over() -> str:
    steps = section(_body(), "First launch, with specs")
    start = steps.index("11. Hand over.")
    end = steps.find("\n\n", start)
    return steps[start:] if end < 0 else steps[start:end]


def test_the_hand_over_keeps_the_hand_and_asks_amend_or_approve() -> None:
    hand_over = _hand_over()
    assert "Then stop" not in hand_over
    assert (
        "keep the hand and ask: amend, or approve by launching `/surface-execute`, whose launch"
        " alone approves this revision" in hand_over
    )


def test_a_change_asked_at_hand_over_is_an_amendment_then_the_same_question() -> None:
    bullets = [line.strip() for line in _hand_over().splitlines() if line.strip().startswith("- ")]
    change = next(line for line in bullets if "asks for a change" in line)
    taken, again = _positions(
        change, ['is an amendment: take it as "Taking an amendment" says', "ask the same question"]
    )
    assert taken < again
    taking = section(_body(), "Taking an amendment")
    assert "and on to step 11" in taking


def test_a_question_at_hand_over_records_nothing_and_a_doubt_is_asked() -> None:
    bullets = [line.strip() for line in _hand_over().splitlines() if line.strip().startswith("- ")]
    question = next(line for line in bullets if line.startswith("- A question"))
    assert "is answered from the files, and nothing is recorded" in question
    assert "- In doubt, ask whether the reply is an amendment." in bullets
    agreeing = next(line for line in bullets if "approves nothing" in line)
    assert "the launch of `/surface-execute` approves, and record nothing" in agreeing


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
    assert "ask the developer's instruction in the conversation" in planning
    assert 'under "Instructions after a block"' in planning
    assert "record <plan> resumed" in planning
    assert "take the amendment" in execution
    assert "`/surface-execute` resumes it" in execution


# The sensitive zones this command carries.


def test_a_new_branch_only_from_the_main_branch() -> None:
    steps = section(_body(), "First launch, with specs")
    branch = next(line for line in steps.splitlines() if line.startswith("2. Branch."))
    # The order ADR 0016 gives the script, so the command and the script agree on "main".
    assert "`origin/HEAD`, else `main`, else `master`" in branch
    assert "Launched from the main branch, create a branch" in branch
    assert "From any other branch, stay" in branch
    assert "A new branch comes only from the main branch" in branch


def _branch_step() -> str:
    steps = section(_body(), "First launch, with specs")
    start = steps.index("\n2. Branch.")
    return steps[start : steps.index("\n3. ", start)]


def test_the_branch_is_named_after_the_practice_in_order_of_evidence() -> None:
    # Branches are deleted after merge, so live branches alone miss the practice; the head
    # branches of past pull requests outlive them.
    order = [
        "A convention written in what step 1 read",
        "`gh pr list --state all --author @me --limit 50 --json headRefName`",
        "`gh pr list --state all --limit 50 --json headRefName,author`",
        "Without `gh`, or when it finds no pull request",
        "`git branch -r`",
        "`git log --merges --format=%s -n 50`",
        "Follow the dominant prefix",
        "No evidence at all",
    ]
    branch = _branch_step()
    positions = _positions(branch, order)
    assert positions == sorted(positions)
    assert "stop at the first that answers" in branch
    assert "leaving out the branches of bots" in branch
    assert "matches the nature of the need" in branch
    assert "Reproduce the format of the slug too" in branch


def test_without_evidence_one_question_names_the_branch_and_lands_in_the_interview() -> None:
    branch = _branch_step()
    assert "ask one question before creating the branch" in branch
    assert "recommending `feature/<slug>`" in branch
    # No plan folder yet: the answer reaches `interview.md` once step 5 creates it, and the
    # branch itself keeps a relaunch from asking again.
    assert 'when step 5 creates `interview.md`, write them there under "Git"' in branch
    assert "never asks again: the branch holds the answer" in branch
    git = _template("interview.md").split("\n## Git\n", 1)[1]
    assert "the branch name asked" in git


def test_the_branch_is_found_with_plain_commands_and_no_setting() -> None:
    branch = _branch_step()
    commands = [
        span for span in re.findall(r"`([^`\n]+)`", branch) if span.startswith(("gh ", "git "))
    ]
    assert len(commands) == 4
    for command in commands:
        assert not re.search(r"\$\(|[|;&<>]|\bcd\b|git -C", command), command
    assert "surface.json" not in branch


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


def test_the_blueprint_template_holds_the_nine_sections_and_no_slice() -> None:
    template = _template("blueprint.md")
    headings = _headings(template)
    assert headings == list(BLUEPRINT_SECTIONS)
    _, extractor = (AGENTS / "surface-extractor.md").read_text(encoding="utf-8").split("\n---\n", 1)
    for heading in headings:
        assert heading in extractor
        assert "slice" not in heading.lower()
    assert parse_slice_markers(template) == ()


def test_the_blueprint_template_gathers_the_unchanged_sections_in_one_closing_line() -> None:
    template = _template("blueprint.md")
    opening = template.split("\n## ", 1)[0]
    assert "As long as the feature needs, and no longer." in opening
    always = [heading.split(".", 1)[0] for heading in ALWAYS_WRITTEN]
    assert f"Sections {', '.join(always[:-1])} and {always[-1]} are always written." in opening
    assert "A section from 4 to 8 is written only when the plan changes what it shows" in opening
    assert "under its own number" in opening
    assert "the closing line names the ones left out, and goes when none is" in opening
    assert "A mermaid diagram only when it shows what the prose of its section does not" in opening
    # One closing line, the last of the page, and no section that only says it has no change.
    closing = [line for line in template.splitlines() if line.startswith(CLOSING_LINE)]
    assert closing == [f"{CLOSING_LINE} <the sections from 4 to 8 left out, by name>."]
    assert template.rstrip("\n").endswith(closing[0])
    assert "No change." not in template
    assert "mermaid diagram wherever" not in template


def test_the_blueprint_template_says_which_critical_zones_the_plan_touches() -> None:
    template = _template("blueprint.md")
    nine = template[template.index("## 9. Sensitive zones") :]
    said = "Critical zones touched, among those the repository's agent instructions declare: none."
    assert said in nine
    assert nine.index(said) < nine.index(CLOSING_LINE)


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


# Boundaries: this command writes neither code, nor the blueprint, nor the journal.


def test_the_command_writes_only_in_the_plan_folder() -> None:
    opening = _body().split("\n## ", 1)[0]
    assert "You write only in the plan folder" in opening
    assert "never the code, never `blueprint.md`" in opening
    assert "never `journal.jsonl` (the state script alone writes it)" in opening


# Templates.


@pytest.mark.parametrize("name", ["plan.md", "blueprint.md", "interview.md", "exploration.md"])
def test_every_template_is_cited(name: str) -> None:
    assert f"${{CLAUDE_SKILL_DIR}}/templates/{name}" in _body()


@pytest.mark.parametrize("name", ["plan.md", "blueprint.md", "interview.md"])
def test_every_template_is_written_in_the_language_exploration_names(name: str) -> None:
    assert f"Written in {DOCUMENTS_LANGUAGE}: translate the headings" in _template(name)


def test_exploration_is_the_one_place_the_language_is_written() -> None:
    template = _template("exploration.md")
    assert "Written in the language it names below, in its repository rules" in template
    rules = section(template, "Repository rules")
    language = next(line for line in rules.splitlines() if line.startswith("- Language:"))
    assert "the language of the plan documents, and where it was found" in language
    assert "every agent reads it here" in language


@pytest.mark.parametrize(
    "path",
    [*prompt_files(), *sorted(TEMPLATES.glob("*.md"))],
    ids=lambda path: path.relative_to(SKILLS.parent).as_posix(),
)
def test_no_prompt_follows_the_language_of_the_specs(path: Path) -> None:
    assert FORMER_LANGUAGE_RULE not in path.read_text(encoding="utf-8")


def test_the_extractor_is_given_the_blueprint_template() -> None:
    assert "`${CLAUDE_SKILL_DIR}/templates/blueprint.md`" in section(_body(), "The agents")


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
        "7. Gates",
    ]
    assert parse_slice_markers(template) == (1,)
    assert parse_gates(template) == ("<command>",)


def test_no_section_of_the_plan_is_filled_for_its_own_sake() -> None:
    steps = section(_body(), "First launch, with specs")
    plan = next(line for line in steps.splitlines() if line.startswith("6. Plan."))
    assert "Each section as long as the feature needs, one screen at most" in plan
    assert "none filled for its own sake" in plan
    opening = _template("plan.md").split("\n## ", 1)[0]
    assert "Each section says what the feature needs and no more" in opening


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
