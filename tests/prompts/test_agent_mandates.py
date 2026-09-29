"""What the bodies of the agent definitions must say.

Prompt behavior is judged end to end; these tests hold what can be read: the classification of a
finding, the paths the reviewer writes, the rules of the executor, and calls of the state script
that its parser accepts.
"""

import pytest
from chain_contract import BREAK_QUESTION, DEFECT_QUESTION, NO_FINDING_END, REVIEWER_WRITES
from prompt_support import (
    ROLES,
    call_arguments,
    marked_block,
    prompt_calls,
    read_agent,
    section,
)

from surface_status.cli import UsageError, build_parser

# Subcommands a prompt may call before the script implements them. Once implemented their calls
# parse, the strict xfail fails, and the entry must go: nothing stays pending silently.
PENDING: dict[str, str] = {}


def _all_calls() -> list[tuple[str, str]]:
    """Every script call of the agents and of the skills, the calls a skill injects included."""
    return prompt_calls()


def _call_param(name: str, call: str) -> object:
    subcommand = call_arguments(call)[0]
    marks: list[pytest.MarkDecorator] = []
    if subcommand in PENDING:
        marks.append(
            pytest.mark.xfail(strict=True, reason=f"`{subcommand}`: {PENDING[subcommand]}")
        )
    return pytest.param(name, call, marks=marks, id=f"{name}: {call}")


# The reviewer: the classification of a finding, the paths it writes, the amendment check.


def test_reviewer_holds_the_classification_of_a_finding() -> None:
    _, body = read_agent("surface-reviewer")
    classifying = section(body, "Classifying a finding").lower()
    for question in (BREAK_QUESTION, DEFECT_QUESTION):
        assert question.lower() in classifying
    assert f"{BREAK_QUESTION} yes: a contract break".lower() in classifying
    for outcome in ("contract break", "a defect, the code is fixed", "a deviation, the plan is"):
        assert outcome in classifying
    assert "when in doubt between deviation and break, classify as a break" in classifying
    assert "never a style preference" in classifying
    assert "file and line" in classifying


def test_reviewer_leads_a_review_with_no_finding_to_the_conform_state() -> None:
    _, body = read_agent("surface-reviewer")
    writing = section(body, "What you write in a review")
    no_finding = next(line for line in writing.splitlines() if line.startswith("- No finding"))
    assert "`conformity.md`" in no_finding
    assert NO_FINDING_END in no_finding


def test_reviewer_names_every_path_it_writes() -> None:
    _, body = read_agent("surface-reviewer")
    for path in REVIEWER_WRITES:
        assert f"`{path}`" in body


def test_reviewer_runs_the_amendment_check_with_the_checker_rule() -> None:
    _, reviewer = read_agent("surface-reviewer")
    _, checker = read_agent("surface-checker")
    check = section(reviewer, "The amendment check")
    assert "since the last approval must leave `overview.md` true" in check
    assert "`.claude/surface.md`" in check
    assert marked_block(check, "checker-rule") == marked_block(checker, "checker-rule")


def test_reviewer_does_not_raise_a_refused_break_again() -> None:
    _, body = read_agent("surface-reviewer")
    assert "`plan-change-refused`" in section(body, "What you read")
    assert "never raise it again as a break" in section(body, "Classifying a finding")


# Every role: what it writes, what it never touches, and a bounded return.


@pytest.mark.parametrize("name", sorted(ROLES))
def test_every_role_starts_from_files_and_returns_a_few_lines(name: str) -> None:
    _, body = read_agent(name)
    assert "no conversation behind you" in body
    returned = [line for line in section(body, "What you return").splitlines() if line.strip()]
    assert 0 < len(returned) <= 4


@pytest.mark.parametrize(
    ("name", "writes"),
    [
        ("surface-extractor", "`overview.md` in the plan folder, and nothing else"),
        ("surface-checker", "One report, and nothing else"),
        ("surface-reviewer", "you write your reports"),
    ],
)
def test_judgment_roles_write_only_their_own_files(name: str, writes: str) -> None:
    _, body = read_agent(name)
    assert writes in body
    assert "journal.jsonl`" in body


def test_executor_never_modifies_the_overview() -> None:
    _, body = read_agent("surface-executor")
    never = section(body, "What you never do")
    assert "Modify `overview.md`" in never
    assert "in the foreground, with a timeout" in never


def test_executor_runs_plain_commands_the_permission_rules_can_read() -> None:
    _, body = read_agent("surface-executor")
    never = section(body, "What you never do")
    assert "Hide a command from the developer's permission rules" in never
    assert "Write and edit files with Write and Edit" in never
    assert "as plain commands" in never
    assert "never echo it" in never


def test_executor_commits_each_slice_with_its_journal_line_and_amendment() -> None:
    _, body = read_agent("surface-executor")
    slice_steps = section(body, "A slice")
    assert "One commit for the slice" in slice_steps
    assert "`plan.md` if amended, and `journal.jsonl`" in slice_steps
    assert "suspected break" in slice_steps
    assert "Leave your work uncommitted" in slice_steps
    assert "continue them or undo them" in section(body, "Uncommitted work")


# Calls of the state script, by the agents and the skills: only subcommands, events and fields
# its parser accepts.


@pytest.mark.parametrize(("name", "call"), [_call_param(name, call) for name, call in _all_calls()])
def test_prompts_call_the_script_only_as_its_parser_accepts(name: str, call: str) -> None:
    del name  # in the test id
    try:
        build_parser().parse_args(call_arguments(call))
    except UsageError as error:
        pytest.fail(f"`{call}` does not parse: {error}")


def test_the_calls_are_found() -> None:
    callers = {name for name, _ in _all_calls()}
    assert callers >= {"surface-executor", "surface-reviewer", "surface-plan"}
    called = {tuple(call_arguments(call)[:3:2]) for _, call in _all_calls()}
    assert {("record", "slice-done"), ("record", "plan-amended"), ("record", "fix-done")} <= called
    assert {call_arguments(call)[0] for _, call in _all_calls()} >= {"show", "record", "gate"}
