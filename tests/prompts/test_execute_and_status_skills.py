"""The two commands `/surface-execute` and `/surface-status`.

Prompt behavior is judged end to end; these tests hold what can be read: the frontmatter the
Claude Code documentation of skills defines, the order of the execution loop and the states it
leaves to `/surface-plan`, the sensitive zones the loop must honor, and the calls of the state
script the two skills spell (their parsing is tested over every prompt).
"""

import re

import pytest
from chain_contract import EXECUTE, EXECUTION_LOOP, SEEN_BY
from prompt_support import SKILLS, call_arguments, prompt_calls, prompt_files, section

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
SCRIPT = "${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status"
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


# Frontmatter: who starts the commands, and on which model (ADR 0023).


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


def test_execute_pins_sonnet_and_status_pins_no_model() -> None:
    execute, _ = read_skill("surface-execute")
    status, _ = read_skill("surface-status")
    assert execute["model"] == "sonnet"
    assert "model" not in status
    assert "effort" not in status


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
    for event in ("plan-change-proposed", "suspicion-dismissed"):
        assert ("surface-execute", "record", event) in called
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


def test_execute_reads_the_rows_of_its_loop_in_order() -> None:
    rows = _loop_rows()
    positions = [rows.index(row) for row in EXECUTION_LOOP]
    assert positions == sorted(positions)
    assert [row for row in rows if "at launch" in row] == rows[:2]
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
    assert "You never edit a file" in section(body, "Ground rules")
    assert "Only the script writes the journal" in section(body, "Ground rules")


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
    assert "launch a fresh `surface-reviewer` on that single question" in section(body, "A slice")
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
    assert "relaunch `/surface-execute`" in ceiling
    assert "amend the plan with `/surface-plan`" in ceiling
    rows = _loop_rows()
    # Checked before any row that launches an agent; conformity is the one step it lets through.
    assert _row_index(rows, "Ceiling reached") < _row_index(rows, "`executing`")
    assert "recording `conform` is the one step the ceiling lets through" in body


def test_a_break_hands_back_through_surface_plan() -> None:
    rows = _table_rows(section(_execute(), "The loop"))
    proposed = next(action for state, action in rows if state == "`plan-change-proposed`")
    assert proposed.startswith("Stop.")
    assert "`/surface-plan`" in proposed


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
    slice_steps = section(_execute(), "A slice")
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


def test_you_mark_the_pr_ready() -> None:
    body = _execute()
    ready = [line for line in body.splitlines() if "gh pr ready" in line]
    assert len(ready) == 1
    assert "only when `settings.mark_pr_ready` is true" in ready[0]
    assert "Otherwise the developer marks it ready" in ready[0]


def test_every_stop_pushes_and_refreshes_the_pr_description() -> None:
    stopping = section(_execute(), "When the loop stops")
    assert "Push the branch to its upstream" in stopping
    assert "`surface-status pr-body`" in stopping
    assert "`gh pr edit --body-file -`" in stopping
    assert "Nothing else is written on the pull request" in stopping


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


def test_status_records_nothing_but_an_abandonment() -> None:
    calls = [call_arguments(call)[0] for name, call in prompt_calls() if name == "surface-status"]
    assert "record" not in calls
    assert "gate" not in calls
    assert {"show", "check", "abandon", "pr-body"} <= set(calls)
