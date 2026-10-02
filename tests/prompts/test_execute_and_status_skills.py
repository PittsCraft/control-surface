"""The two commands `/surface-execute` and `/surface-status`.

Prompt behavior is judged end to end; these tests hold what can be read: the frontmatter the
Claude Code documentation of skills defines, the order of the execution loop and the states it
leaves to `/surface-plan`, the acts of the developer it takes in the conversation, the sensitive
zones the loop must honor, and the calls of the state script the two skills spell (their parsing
is tested over every prompt).
"""

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest
from chain_contract import (
    CONFORM_EXCEPTION,
    CONFORM_HAND_BACK,
    CORRECTIONS_CEILING,
    DOCUMENTS_LANGUAGE,
    EXECUTE,
    EXECUTION_LOOP,
    IN_CONVERSATION,
    REFUSED_LIST,
    SEEN_BY,
)
from chain_contract import PLAN as PLAN_COMMAND
from cli_support import PLAN, Project
from prompt_support import SKILLS, call_arguments, prompt_calls, prompt_files, section

from surface_status.events import PlanOpened
from surface_status.guards import RefusalCode
from surface_status.machine import TRANSITIONS, Rule, State, apply
from surface_status.resolve import EXECUTE_COMMAND as EXECUTE_SCRIPT_COMMAND
from surface_status.resolve import PLAN_COMMAND as PLAN_SCRIPT_COMMAND
from surface_status.resolve import sees

# Frontmatter fields of a skill, from the reference table of the documentation of skills.
SKILL_FIELDS = {
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
}
# Called from the root of the repository, the path a rule of the project settings can name.
SCRIPT = ".claude/skills/surface-status/scripts/surface-status"
_FIELD = re.compile(r"(?P<key>[a-z][a-z_-]*): (?P<value>\S.*)")


def read_skill(name: str) -> tuple[dict[str, str], str]:
    """Return the flat frontmatter and the body of a skill; keys may hold hyphens."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    head, fence, body = text[4:].partition("\n---\n")
    assert fence, "the frontmatter is not closed"
    fields: dict[str, str] = {}
    for line in head.splitlines():
        match = _FIELD.fullmatch(line)
        assert match is not None, f"not a flat `key: value` line: {line!r}"
        assert match["key"] not in fields, f"duplicated key {match['key']!r}"
        fields[match["key"]] = match["value"].strip()
    return fields, body


# A field a prompt reads in the answer of `show`: "`passes.execution` of `show --json`".
_SHOW_FIELD = re.compile(r"`([a-z_.]+)` of `(?:surface-status )?show(?: <plan>)?(?: --json)?`")


def _execute() -> str:
    return read_skill("surface-execute")[1]


def _status() -> str:
    return read_skill("surface-status")[1]


def _table_rows(text: str) -> list[list[str]]:
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    cells = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]
    return [row for row in cells[1:] if not set(row[0]) <= {"-", ":"}]


def _loop_rows() -> list[str]:
    """First cells of the dispatch table of `/surface-execute`, in order."""
    return [row[0] for row in _table_rows(section(_execute(), "The loop"))]


def _row_index(rows: list[str], needle: str) -> int:
    return next(index for index, row in enumerate(rows) if needle in row)


# Frontmatter: who starts the commands, never on which model (ADR 0031).


@pytest.mark.parametrize("name", ["surface-execute", "surface-status"])
def test_frontmatter_holds_only_fields_the_documentation_defines(name: str) -> None:
    fields, _ = read_skill(name)
    assert set(fields) <= SKILL_FIELDS
    assert fields["name"] == name
    assert len(fields["description"].split()) >= 8


@pytest.mark.parametrize("name", ["surface-execute", "surface-status"])
def test_only_the_developer_starts_the_command(name: str) -> None:
    fields, _ = read_skill(name)
    assert fields["disable-model-invocation"] == "true"


@pytest.mark.parametrize("name", ["surface-execute", "surface-status"])
def test_the_session_keeps_the_model_and_effort_the_developer_chose(name: str) -> None:
    fields, _ = read_skill(name)
    assert "model" not in fields
    assert "effort" not in fields


@pytest.mark.parametrize("name", ["surface-execute", "surface-status"])
def test_the_script_the_body_runs_is_the_one_allowed_tools_grants(name: str) -> None:
    fields, body = read_skill(name)
    assert f"Bash({SCRIPT} *)" in fields["allowed-tools"]
    assert f"`{SCRIPT}`" in body
    # No spawning grant, no blanket grant: each rule names a command.
    assert "Agent" not in fields["allowed-tools"]
    assert all(rule.startswith("Bash(") for rule in fields["allowed-tools"].split(") ") if rule)


def test_both_skills_are_read_by_the_host_neutrality_test() -> None:
    files = {path.parent.name for path in prompt_files() if path.name == "SKILL.md"}
    assert {"surface-execute", "surface-status"} <= files


# Calls of the state script: the parser test of `prompt_calls()` covers every prompt.


def test_the_skill_calls_are_found() -> None:
    called = {(name, *call_arguments(call)[:3:2]) for name, call in prompt_calls()}
    for event in ("plan-approved", "resumed", "review-done", "conform", "blocked"):
        assert ("surface-execute", "record", event) in called
    for event in (
        "plan-change-proposed",
        "suspicion-dismissed",
        "plan-change-refused",
        "plan-change-accepted",
    ):
        assert ("surface-execute", "record", event) in called
    # The executor keeps the reason of a suspected break in the journal, not in its return.
    assert ("surface-executor", "record", "break-suspected") in called
    subcommands = {(name, call_arguments(call)[0]) for name, call in prompt_calls()}
    assert {("surface-execute", word) for word in ("resolve", "show", "gate", "commits")} <= (
        subcommands
    )
    assert ("surface-status", "abandon") in subcommands


# The dispatch loop, read top to bottom, and the states it leaves to `/surface-plan`.


def test_execute_has_a_row_for_every_state_in_progress() -> None:
    rows = _table_rows(section(_execute(), "The loop"))
    for state, commands in SEEN_BY.items():
        action = next(action for first, action in rows if f"`{state}`" in first)
        if EXECUTE not in commands:
            assert action.startswith("Stop: this plan belongs to `/surface-plan`"), state


def test_resolve_finds_a_plan_for_the_commands_that_act_on_its_state() -> None:
    # Relaunched without an argument, a command finds the plans its prompt acts on, no others.
    # A block is seen by `/surface-execute` only when it stopped the execution.
    opened = apply(None, PlanOpened(slug="x"))
    names = {PLAN_COMMAND: PLAN_SCRIPT_COMMAND, EXECUTE: EXECUTE_SCRIPT_COMMAND}
    for state, commands in SEEN_BY.items():
        found = replace(opened, state=State(state), before_blocked=State.EXECUTING)
        for command, name in names.items():
            assert sees(name, found) is (command in commands), (state, command)


def test_execute_reads_the_rows_of_its_loop_in_order() -> None:
    rows = _loop_rows()
    positions = [rows.index(row) for row in EXECUTION_LOOP]
    assert positions == sorted(positions)
    # An alarm stops the loop before anything is recorded, the approval included.
    assert "`alarms`" in rows[0]
    assert [row for row in rows if "at launch" in row] == rows[1:3]
    assert "they apply only once, at launch" in section(_execute(), "The loop")


def test_execute_resumes_from_files_never_from_the_conversation() -> None:
    rules = section(_execute(), "Ground rules")
    assert "Before every step, read it again" in rules
    assert "Never decide a step from memory of this conversation" in rules
    assert "the files decide" in rules
    assert "from memory of this conversation" in _status()


def test_execute_writes_neither_code_nor_plan() -> None:
    body = _execute()
    assert "You write neither code nor plan" in body
    rules = section(body, "Ground rules")
    assert "You edit one file only: `interview.md` of the plan folder" in rules
    assert "Never code, never `plan.md`, never `blueprint.md`" in rules
    assert "`interview.md` for a decision of the developer" in rules
    assert "Only the script writes the journal" in rules


def test_execute_speaks_the_developers_language_and_quotes_their_decisions() -> None:
    rules = section(_execute(), "Ground rules")
    assert "You speak to the developer in the language they write in" in rules
    assert DOCUMENTS_LANGUAGE in rules
    assert "quoted in their words, then translated" in rules
    declined = _proposal_replies()["Declined"]
    assert "quoted in the developer's words and translated" in declined


def test_execute_writes_under_headings_the_interview_template_holds() -> None:
    template = (SKILLS / "surface-plan" / "templates" / "interview.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^## (.+)$", template, re.MULTILINE))
    lines = [line for line in _execute().splitlines() if "`interview.md`" in line]
    under = set(re.findall(r'under "([^"]+)"', "\n".join(lines)))
    assert under == {"Plan change decisions"}
    assert under <= headings


def test_only_the_launch_approves_and_a_relaunch_resumes() -> None:
    opening = _execute().split("\n## ", 1)[0]
    assert "the developer's launch is the approval" in opening
    assert "never by a sentence of the conversation" in opening
    assert "after a dead session, relaunching it is the way to resume" in opening


def test_a_fresh_agent_for_every_slice_review_and_fix() -> None:
    body = _execute()
    rules = section(body, "Ground rules")
    assert "A fresh agent for every slice, every review, every fix" in rules
    assert "`model` set to that role's model under `settings.models`" in rules
    assert "never a summary of this conversation" in rules
    assert "Never resume an agent" in rules
    for heading, role in (
        ("A slice", "surface-executor"),
        ("A review", "surface-reviewer"),
        ("A fix", "surface-executor"),
    ):
        assert f"Launch a fresh `{role}`" in section(body, heading)
    suspected = section(body, "A suspected break")
    assert "launch a fresh `surface-reviewer` on that single question" in suspected
    # The planning roles belong to `/surface-plan`.
    assert "surface-extractor" not in body
    assert "surface-checker" not in body


def test_approval_is_announced_then_recorded_once() -> None:
    rows = _table_rows(section(_execute(), "The loop"))
    approve = next(action for state, action in rows if "`awaiting-approval`, at launch" in state)
    assert approve.index("the revision you approve") < approve.index("plan-approved")


def test_several_plans_ask_the_developer() -> None:
    finding = section(_execute(), "Finding the plan")
    assert "The plan the developer names wins" in finding
    assert "several `candidates`" in finding
    assert "ask the developer to relaunch `/surface-execute` naming one, and stop" in finding


def test_the_ceiling_blocks_and_hands_back_to_the_developer() -> None:
    body = _execute()
    ceiling = section(body, "At the ceiling")
    assert "`surface-status record <plan> blocked" in ceiling
    assert "the developer takes the hand back" in ceiling
    assert "Launch no fix" in ceiling
    blocked, stopped, asked = _positions(
        ceiling,
        [
            "record <plan> blocked",
            'Do the steps of "When the loop stops"',
            "Keep the hand and ask: resume, or amend the plan, with your recommendation",
        ],
    )
    assert blocked < stopped < asked
    bullets = [line.strip() for line in ceiling.splitlines() if line.strip().startswith("- ")]
    resume = next(line for line in bullets if line.startswith("- Resume:"))
    recorded, goes_on = _positions(
        resume, ["`surface-status record <plan> resumed`", "back to the loop in this session"]
    )
    assert recorded < goes_on
    amend = next(line for line in bullets if line.startswith("- Amend:"))
    assert "run `/surface-plan <amendment>`" in amend
    assert "Record nothing, and stop" in amend
    question = next(line for line in bullets if line.startswith("- A question"))
    assert "nothing is recorded" in question
    assert 'the row "`blocked` during execution, at launch"' in ceiling
    rows = _loop_rows()
    # Checked before any row that launches an agent; conformity is the one step it lets through.
    assert _row_index(rows, "Ceiling reached") < _row_index(rows, "`executing`")
    assert "recording `conform` is the one step the ceiling lets through" in body
    # The script records the pass after the ceiling, which hands back: the ceiling is passed.
    assert "`passes.execution` of `show --json` is more than `passes.ceiling`" in body


def test_the_reason_of_a_suspected_break_is_read_from_a_field_show_gives() -> None:
    """A relaunch finds the executor's reason in `show --json`, under the names the loop reads."""
    golden = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "show-suspected.json"
    shown = json.loads(golden.read_text(encoding="utf-8"))
    assert set(shown["pending_suspicion"]) == {"slice", "why"}
    body = _execute()
    assert "`pending_suspicion` of `show --json`" in section(body, "The loop")
    assert "`slice` and `why` of `pending_suspicion`" in section(body, "A suspected break")


def _positions(text: str, needles: list[str]) -> list[int]:
    positions = [text.find(needle) for needle in needles]
    missing = [needle for needle, at in zip(needles, positions, strict=True) if at < 0]
    assert not missing, f"not found: {missing}"
    return positions


def _proposal_replies() -> dict[str, str]:
    proposal = section(_execute(), "A plan change proposal")
    bullets = [line.strip() for line in proposal.splitlines() if line.strip().startswith("- ")]
    return {line[2:].split(":", 1)[0]: line for line in bullets}


def test_a_proposal_is_put_to_the_developer_in_the_conversation() -> None:
    rows = _table_rows(section(_execute(), "The loop"))
    proposed = next(action for state, action in rows if state == "`plan-change-proposed`")
    assert proposed == 'See "A plan change proposal".'
    proposal = section(_execute(), "A plan change proposal")
    assert "`pending_proposal` of `show --json`" in proposal
    stopped, presented, asked = _positions(
        proposal,
        [
            'first do the steps of "When the loop stops"',
            "present the proposal yourself, at the level of the blueprint",
            "Ask: accept or decline, with your recommendation",
        ],
    )
    assert stopped < presented < asked
    assert "the proof, not the code" in proposal


def test_a_decision_already_written_is_not_asked_again() -> None:
    proposal = section(_execute(), "A plan change proposal")
    assert "already holds the decision on this proposal" in proposal
    assert "nothing is asked again" in proposal
    interrupted = section(_execute(), "Interrupted work")
    assert "A decision of the developer in `interview.md`" in interrupted


def test_a_declined_proposal_is_written_recorded_and_the_loop_goes_on() -> None:
    declined = _proposal_replies()["Declined"]
    positions = _positions(
        declined,
        [
            "ask the reason in one line",
            'into `interview.md` under "Plan change decisions"',
            'record <plan> plan-change-refused --why "<reason>"',
            "commit `interview.md` with the journal",
            "Back to the loop, in this session",
        ],
    )
    assert positions == sorted(positions)


def test_an_accepted_proposal_is_written_recorded_then_goes_to_surface_plan() -> None:
    accepted = _proposal_replies()["Accepted"]
    positions = _positions(
        accepted,
        [
            'into `interview.md` under "Plan change decisions"',
            "record <plan> plan-change-accepted",
            "commit `interview.md` with the journal",
            'stop as "When the loop stops" says',
            "run `/surface-plan`, which draws the next revision",
        ],
    )
    assert positions == sorted(positions)
    assert "You draw no revision" in accepted
    assert "approved by a new launch of `/surface-execute`" in accepted


def test_a_question_on_a_proposal_records_nothing() -> None:
    question = next(
        line for key, line in _proposal_replies().items() if key.startswith("A question")
    )
    assert "is answered from the files, and nothing is recorded" in question
    assert "In doubt, ask whether the reply is a decision" in question


# The acts of the developer taken in the conversation, against the state script's table.


def _command_records(command: str) -> set[str]:
    """Return the events a command records, the command named like its skill folder."""
    return {
        call_arguments(call)[2]
        for name, call in prompt_calls()
        if name == command and call_arguments(call)[0] == "record"
    }


def test_every_act_in_the_conversation_is_legal_where_it_is_recorded() -> None:
    for command, state, event in IN_CONVERSATION:
        assert State(state) in TRANSITIONS[event], (command, state, event)
        assert command in SEEN_BY[state], (command, state)
        assert event in _command_records(command), (command, event)
        assert event != "plan-approved"


def test_what_the_conversation_cannot_take_goes_to_surface_plan() -> None:
    accepted = TRANSITIONS["plan-change-accepted"][State.PLAN_CHANGE_PROPOSED]
    assert accepted is State.DRAFTING
    assert SEEN_BY[accepted.value] == frozenset({PLAN_COMMAND})
    # A resumption returns to the state before the block, which the command that blocked sees.
    assert TRANSITIONS["resumed"][State.BLOCKED] is Rule.BEFORE_BLOCKED


def test_a_refusal_is_reported_never_worked_around() -> None:
    body = _execute()
    assert "A refusal is never worked around: stop and report it" in body
    assert "on a refusal of the script" in section(body, "When the loop stops")


# The sensitive zones the loop honors.


def test_an_agent_may_undo_uncommitted_work() -> None:
    body = _execute()
    interrupted = section(body, "Interrupted work")
    assert "belongs to the interrupted step" in interrupted
    assert "continues or undoes it" in interrupted
    assert "`git status` shows uncommitted work" in section(body, "A slice")
    assert "belongs to the interrupted fix" in section(body, "A fix")


def test_your_manual_commits_are_reviewed() -> None:
    review = section(_execute(), "A review")
    assert "`base` of `surface-status commits <plan> --json`" in review
    assert "everything the branch changes against its merge base" in review
    assert "the developer's own commits included" in review


def test_unfinished_code_may_be_committed() -> None:
    slice_steps = section(_execute(), "A suspected break")
    confirmed = next(line for line in slice_steps.splitlines() if "`confirmed`" in line)
    assert "plan-change-proposed" in confirmed
    assert "the unfinished work of the slice" in confirmed
    dismissed = next(line for line in slice_steps.splitlines() if "`dismissed`" in line)
    assert "not the work" in dismissed


def test_full_gates_run_at_every_pass() -> None:
    body = _execute()
    rows = _loop_rows()
    assert _row_index(rows, "no green gate run") < _row_index(rows, "gates green")
    assert "`surface-status gate <plan>` runs the project's full gates" in section(body, "Gates")
    assert "runs the full gates once at its end" in section(body, "A fix")
    assert "never end the turn waiting for a notification" in section(body, "Gates")


def test_a_report_of_the_chain_that_fails_a_gate_stops_the_loop() -> None:
    fixing = section(_execute(), "A fix")
    assert "The return `a report fails a gate` is a stop" in fixing


def test_every_stop_pushes_and_refreshes_the_pr_description() -> None:
    stopping = section(_execute(), "When the loop stops")
    assert "Push the branch to its upstream" in stopping
    assert "`surface-status pr-body`" in stopping
    assert "`gh pr edit --body-file -`" in stopping
    assert "Nothing else is written on the pull request" in stopping


def test_conform_hands_back_in_one_line_and_leaves_the_ready_mark_to_the_developer() -> None:
    body = _execute()
    conformity = section(body, "Conformity")
    assert f"hand back in one line: {CONFORM_HAND_BACK}" in conformity
    assert "one it cannot prove is a finding" in conformity
    assert "nothing asks the developer to read it" in conformity
    stopping = section(body, "When the loop stops")
    assert "Never mark the pull request ready, since that triggers the CI" in stopping


def test_conform_says_the_one_exception_the_code_of_the_critical_zones() -> None:
    conformity = section(_execute(), "Conformity")
    assert f"Say the one exception in one sentence: {CONFORM_EXCEPTION}" in conformity
    assert (
        "whose changed files the pull request description lists, when there are any" in conformity
    )
    assert "for the developer to read themselves" in conformity


def test_a_refused_list_of_critical_files_goes_to_a_fresh_reviewer() -> None:
    body = _execute()
    conformity = section(body, "Conformity")
    assert f"Refused with the code `{RefusalCode.CRITICAL_FILES.value}`" in conformity
    assert "is malformed or names a file the branch did not change" in conformity
    assert "The developer is not asked to repair an agent's list" in conformity
    assert "only a reviewer edits a reviewer's report" in conformity
    assert "launch a fresh `surface-reviewer`. Its mandate" in conformity
    mandate = "Its mandate: the plan folder, the base commit"
    assert f"{mandate} (`base` of `surface-status commits <plan> --json`)" in conformity
    assert f"and the mode, {REFUSED_LIST}, with the refusal's reason" in conformity
    assert "It corrects that list and nothing else, and records nothing" in conformity
    assert "when it returns, record `conform` again, as above" in conformity
    assert "with `conformity.md` when its content is not committed yet" in conformity
    assert f"every suspected break and every {REFUSED_LIST.removeprefix('a ')}" in section(
        body, "Ground rules"
    )


def test_the_corrections_of_a_refused_list_are_bounded_by_the_ceiling_of_passes() -> None:
    conformity = section(_execute(), "Conformity")
    again = "Refused again: a fresh reviewer again, with the new reason"
    assert f"{again}, {CORRECTIONS_CEILING}" in conformity
    assert "the one setting that bounds what the loop does on its own bounds this too" in conformity
    # No number of its own: the ceiling is the one `show` gives.
    assert re.search(r"\b(once|twice|three|\d+) (times?|reviewers?)\b", conformity) is None
    assert "Keep that count yourself" in conformity
    assert "a refused `conform` leaves no line in the journal" in conformity
    assert "these attempts do not raise `passes.execution`" in conformity
    after = "Still refused after them: stop and report the reason to the developer."
    assert conformity.rstrip().endswith(after)


def test_the_reviewers_that_correct_a_list_are_not_taken_for_steps_without_progress() -> None:
    body = _execute()
    rule = next(line for line in body.splitlines() if line.startswith("- No progress"))
    assert "Never launch the same step twice in a row without progress" in rule
    assert 'The reviewers "Conformity" sends to correct a refused list are the exception' in rule
    assert "they move no line, the record that follows them does" in rule
    assert "their own bound is there" in rule


def test_no_prompt_makes_conformity_a_required_reading() -> None:
    reading = re.compile(r"\b(read|reads|reading)\b[^.]*`conformity\.md`")
    for path in prompt_files():
        text = path.read_text(encoding="utf-8")
        assert reading.search(text) is None, path


# `/surface-status`: the state, the check, and an abandonment only once confirmed.


def test_status_abandons_only_after_confirmation() -> None:
    abandoning = section(_status(), "Abandoning a plan")
    assert "Record nothing without an explicit yes" in abandoning
    confirm = abandoning.index("Ask the developer to confirm")
    assert confirm < abandoning.index("`surface-status abandon <plan>")
    assert "the conformity check fails from then on" in abandoning
    assert "the alarm stays even if that code is removed" in abandoning
    assert "`surface-status pr-body`" in abandoning
    assert "Commit the journal alone" in abandoning


def test_every_field_of_show_a_prompt_reads_is_in_its_answer(tmp_path: Path) -> None:
    cited = {
        match.group(1)
        for path in prompt_files()
        for match in _SHOW_FIELD.finditer(path.read_text(encoding="utf-8"))
    }
    assert "gates" in cited
    project = Project(tmp_path)
    project.reach("executing")
    answer = project.run("show", PLAN).json()
    for field in sorted(cited):
        value = answer
        for key in field.split("."):
            assert key in value, field
            value = value[key]


def test_status_records_nothing_but_an_abandonment() -> None:
    calls = [call_arguments(call)[0] for name, call in prompt_calls() if name == "surface-status"]
    assert "record" not in calls
    assert "gate" not in calls
    assert {"show", "check", "abandon", "pr-body"} <= set(calls)


# The turn the developer launched: the loop asks for the foreground and claims no model (ADR 0031).


def test_the_loop_asks_for_the_foreground() -> None:
    rules = section(_execute(), "Ground rules")
    assert "Ask for the foreground, `run_in_background` false" in rules


def test_the_loop_neither_pins_nor_checks_the_session_model() -> None:
    body = _execute()
    assert "Sonnet" not in body
    assert "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS" not in body
    assert "/model" not in body
