"""The `surface-plan` command and its templates (ADR 0031).

Prompt behavior is judged end to end. These tests hold what can be read: the frontmatter against
the fields the Claude Code documentation of skills defines, the state injected at load, the
planning sequence and the states this command resumes, its staying in the conversation, the
sensitive zones it carries, and templates the script and the agents can read.
"""

import re
from fnmatch import fnmatchcase
from pathlib import Path

import pytest
from chain_contract import (
    BLUEPRINT_ASPECTS,
    BLUEPRINT_CLOSING,
    BLUEPRINT_OPENING,
    CLOSING_LINE,
    DOCUMENTS_LANGUAGE,
    FORMER_LANGUAGE_RULE,
    LANGUAGE_SOURCES,
    PLAN,
    PLAN_AGENT,
    PLAN_MINIMUM,
    PLANNING_EVENTS,
    SEEN_BY,
)
from prompt_support import (
    AGENTS,
    BUILT_IN_ROLES,
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
        "`Plan` agent",
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


def test_the_interview_asks_what_a_user_of_the_feature_would_see() -> None:
    steps = section(_body(), "First launch, with specs")
    interview = next(line for line in steps.splitlines() if line.startswith("5. Interview."))
    # What separates a rule of the developer from a matter of implementation is said before the
    # rule that stops the interview: an order or a frequency is never filed as implementation.
    theirs, settled, question, stop, assumption = _positions(
        interview,
        [
            "A point is the developer's when it is a rule that a user of the feature",
            "What the specs or the code settle, its closest precedent included, is not asked",
            "What neither settles is a question, however obvious its answer looks",
            "Stop when what remains is a matter of implementation you can decide",
            "It goes to the plan as an assumption",
        ],
    )
    assert theirs < settled < question < stop < assumption
    assert "or a program that reads what it writes, would see applied" in interview
    assert "which neither a user nor such a program would see" in interview
    assert "an order, ties included, a number, a frequency or a limit" in interview
    assert "your pick is its recommendation, never an assumption of the plan" in interview


def test_every_planning_step_goes_to_a_fresh_agent_on_the_models_of_the_settings() -> None:
    agents = section(_body(), "The agents")
    fresh = "A fresh agent for each draft of the plan, each extraction and each cross-check"
    assert fresh in agents
    assert "`model` its value in `settings.models`" in agents
    assert "file paths only, never the conversation" in agents
    for role in ("surface-extractor", "surface-checker"):
        assert f"`{role}`" in agents
        assert (AGENTS / f"{role}.md").is_file()
        assert f"`{ROLES[role]}`" in agents
        assert hasattr(Models(), ROLES[role])


# The plan: drafted by the agent built into Claude Code, held to the minimum the chain reads.


def test_the_plan_is_drafted_by_the_built_in_agent_on_the_model_of_the_settings() -> None:
    agents = section(_body(), "The agents")
    given = next(line for line in agents.splitlines() if line.startswith(f"- `{PLAN_AGENT}`"))
    assert "the agent built into Claude Code, which the chain neither installs nor defines" in given
    assert "`${CLAUDE_SKILL_DIR}/templates/plan.md`" in given
    assert "that file is its whole mandate" in given
    assert f"`{BUILT_IN_ROLES[PLAN_AGENT]}`" in agents
    assert hasattr(Models(), BUILT_IN_ROLES[PLAN_AGENT])
    opening = _body().split("\n## ", 1)[0]
    assert "The plan is drafted by a fresh `Plan` agent, and you write it as returned" in opening


def _plan_step() -> str:
    steps = section(_body(), "First launch, with specs")
    return steps[steps.index("6. Plan.") : steps.index("7. Extraction.")]


def test_the_command_writes_the_plan_as_returned_and_checks_only_the_minimum() -> None:
    plan = _plan_step()
    positions = _positions(
        plan,
        [
            "Launch a fresh `Plan` agent",
            "Write that return to `plan.md` as it is",
            "Then check the minimum the chain reads, below, and nothing else",
            "launch a fresh agent once more; then tell the developer and stop",
        ],
    )
    assert positions == sorted(positions)
    assert "since it has no write tool" in plan
    assert "its design and its form are the agent's, and you rework neither" in plan
    # What the script or the repository's checks could not read is repaired, and never told.
    assert "Two repairs are not a rework, and are not reported to the developer" in plan
    assert "when the markers arrived escaped, `&lt;!--` for `<!--`, the whole return did" in plan
    assert "every entity is written as its character, once" in plan
    assert "a path of the machine becomes its path from the root of the repository" in plan
    assert "or a neutral form such as `/path/to/...` when it lies outside it" in plan
    assert "every path is written from the root of the repository" in _template("plan.md")
    for held in (
        "The acceptance criteria, numbered, those of the specs and the interview",
        "Each slice behind its `<!-- slice:N -->` marker, alone on its line",
        "enough for an agent that starts fresh",
        "A slice number the journal has seen is never reused",
        "The `gates` block, which holds the gates you found and no other",
        "The documents' language, and no code beyond a signature or a schema fragment",
        "the slices already done kept under their numbers",
    ):
        assert held in plan, held


def test_the_gates_are_the_commands_and_never_the_agents_choice() -> None:
    gates = section(_body(), "The gates")
    assert "write them in `exploration.md` as the gates of the plan" in gates
    assert "You name the gates, the agent that drafts the plan does not choose them" in gates
    assert "you correct it when the agent wrote others" in gates
    assert "the agent does not choose them" in section(_template("plan.md"), "Gates")
    rules = section(_template("exploration.md"), "Repository rules")
    assert "Then the gates of the plan: the commands its `gates` block will hold" in rules


def test_the_exploration_stops_at_what_the_interview_needs() -> None:
    steps = section(_body(), "First launch, with specs")
    exploration = next(line for line in steps.splitlines() if line.startswith("4. Exploration."))
    assert "as far as the interview needs" in exploration
    assert "so that no question is asked that the code answers" in exploration
    assert "is left to the agent that drafts the plan" in exploration
    touched = section(_template("exploration.md"), "What the feature touches")
    assert "As far as the interview needs" in touched
    assert "is read by the agent that drafts the plan" in touched


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
            "stay in the conversation: present what does not converge",
            "ask the developer's instruction in the conversation",
            '"After a block"',
        ],
    )
    assert positions == sorted(positions)
    assert "`/surface-plan`" not in ceiling


# The hand-over: the command stays in the conversation, and only the launch of `/surface-execute`
# approves.


def _hand_over() -> str:
    steps = section(_body(), "First launch, with specs")
    start = steps.index("11. Hand over.")
    end = steps.find("\n\n", start)
    return steps[start:] if end < 0 else steps[start:end]


def test_the_hand_over_stays_in_the_conversation_and_asks_amend_or_approve() -> None:
    hand_over = _hand_over()
    assert "Then stop" not in hand_over
    assert "Say in one line how the body of the blueprint is cut, and why" in hand_over
    assert (
        "stay in the conversation and ask: amend, or approve by launching `/surface-execute`, whose"
        " launch alone approves this revision" in hand_over
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
    assert "The plan is over" in actions["conformant"]
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


def test_an_amendment_when_it_is_not_the_developers_turn_is_explained_and_refused() -> None:
    body = _body()
    outside = section(body, "Not your turn")
    assert "only when it is their turn: awaiting approval, or blocked" in outside
    for state in ("executing", "reviewing", "fixing"):
        assert f"`{state}`" in outside
    assert "record nothing" in outside
    assert "wait for the loop to stop" in outside
    assert "abandon the plan with `/surface-status`" in outside
    assert section(body, "Taking an amendment").startswith(
        "\nOnly in `awaiting-approval`, or `blocked` during execution."
    )


def test_the_blueprint_template_holds_the_frame_around_a_body_and_no_slice() -> None:
    template = _template("blueprint.md")
    headings = _headings(template)
    assert headings[: len(BLUEPRINT_OPENING)] == list(BLUEPRINT_OPENING)
    assert headings[-1] == BLUEPRINT_CLOSING
    body = headings[len(BLUEPRINT_OPENING) : -1]
    assert body == ["<A section of the body, titled in the words of the feature>"]
    _, extractor = (AGENTS / "surface-extractor.md").read_text(encoding="utf-8").split("\n---\n", 1)
    for heading in (*BLUEPRINT_OPENING, BLUEPRINT_CLOSING):
        assert heading in extractor
    for heading in headings:
        assert "slice" not in heading.lower()
        assert not heading[0].isdigit(), heading
    assert parse_slice_markers(template) == ()


def test_the_blueprint_template_names_the_aspects_left_alone_in_one_closing_line() -> None:
    template = _template("blueprint.md")
    opening = template.split("\n## ", 1)[0]
    assert "As long as the feature needs, and no longer." in opening
    assert "No heading carries a number." in opening
    assert "The three opening sections and the closing one are always written." in opening
    assert "the body is cut for the feature" in opening
    aspects = f"{', '.join(BLUEPRINT_ASPECTS[:-1])} and {BLUEPRINT_ASPECTS[-1]}"
    assert f"The closing line names the aspects the plan leaves alone, among {aspects}" in opening
    assert "and goes when the plan changes all five" in opening
    assert "A mermaid diagram where what it shows has a shape that prose flattens" in opening
    # One closing line, the last of the page, and no section that only says it has no change.
    closing = [line for line in template.splitlines() if line.startswith(CLOSING_LINE)]
    assert closing == [f"{CLOSING_LINE} <the aspects the plan leaves alone, by name>."]
    assert template.rstrip("\n").endswith(closing[0])
    assert "No change." not in template
    assert "mermaid diagram wherever" not in template


def test_the_blueprint_template_says_which_critical_zones_the_plan_touches() -> None:
    template = _template("blueprint.md")
    zones = template[template.index(f"## {BLUEPRINT_CLOSING}") :]
    said = "Critical zones touched, among those the repository's agent instructions declare: none."
    assert said in zones
    assert zones.index(said) < zones.index(CLOSING_LINE)


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


def test_the_plan_template_holds_the_minimum_the_chain_reads_and_readable_markers() -> None:
    template = _template("plan.md")
    headings = _headings(template)
    assert headings == list(PLAN_MINIMUM)
    for heading in headings:
        assert not heading[0].isdigit(), heading
    assert parse_slice_markers(template) == (1,)
    assert parse_gates(template) == ("<command>",)
    criteria = section(template, "Acceptance criteria")
    assert "Numbered, taken from the specs and the interview" in criteria
    assert "cite them by number" in criteria
    slices = section(template, "Slices")
    fresh = "enough for an agent that starts fresh, which reads files and never a conversation"
    assert fresh in slices
    assert "A slice number is never reused" in slices


def test_the_plan_template_leaves_the_rest_to_the_agent_that_drafts_it() -> None:
    opening = _template("plan.md").split("\n## ", 1)[0]
    assert "The agent that drafts the plan designs it and lays it out as it sees fit" in opening
    assert "each as long as the feature needs, none filled for its own sake" in opening
    assert "The chain reads three things only" in opening
    assert "No code beyond a signature or a schema fragment" in opening
    assert "it returns the plan whole as its answer, and nothing around it" in opening
    assert "the command that launched it writes `plan.md`" in opening


def test_the_plan_template_keeps_the_slices_already_done_across_revisions() -> None:
    opening = _template("plan.md").split("\n## ", 1)[0]
    assert "When `plan.md` already exists, the agent drafts its next revision" in opening
    assert "every amendment and every accepted plan change of `interview.md`" in opening
    built = "A slice that a `slice-done` line of `journal.jsonl` records is built"
    assert f"{built}: it stays, under its number" in opening


@pytest.mark.parametrize(
    "path",
    [*prompt_files(), *sorted(TEMPLATES.glob("*.md"))],
    ids=lambda path: path.relative_to(SKILLS.parent).as_posix(),
)
def test_no_prompt_names_a_section_of_a_document_by_a_number(path: Path) -> None:
    # A plan and a blueprint are laid out for the feature: a number would point elsewhere in the
    # next one.
    assert re.search(r"\bsections? [0-9]", path.read_text(encoding="utf-8"), re.IGNORECASE) is None


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
