"""What the bodies of the agent definitions must say.

Prompt behavior is judged end to end; these tests hold what can be read: the classification of a
finding, the paths the reviewer writes, the rules of the executor, and calls of the state script
that its parser accepts.
"""

import re
from pathlib import Path

import pytest
from chain_contract import (
    BLUEPRINT_ASPECTS,
    BLUEPRINT_CLOSING,
    BLUEPRINT_ON_THE_COMMITS,
    BLUEPRINT_OPENING,
    BREAK_QUESTION,
    CHAIN_REPORTS,
    COMMIT_FORM,
    CRITICAL_FILES_OF_THE_BRANCH,
    CRITICAL_ZONES_OF_THE_PLAN,
    DEFECT_QUESTION,
    DOCUMENTS_LANGUAGE,
    NO_FINDING_END,
    REFUSED_LIST,
    REVIEWER_MODES,
    REVIEWER_WRITES,
    TOUCHES_NONE,
    UNNAMED_ZONE,
    WORK_FROM_TRANSLATION,
)
from prompt_support import (
    ROLES,
    call_arguments,
    marked_block,
    prompt_calls,
    prompt_files,
    read_agent,
    section,
    split_agent,
)

from surface_status.cli import UsageError, build_parser
from surface_status.plan_folder import CRITICAL_FILES_TAG, parse_critical_files

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


def test_reviewer_leads_a_review_with_no_finding_to_the_conformant_state() -> None:
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
    assert "since the last approval must leave `blueprint.md` true" in check
    assert marked_block(check, "checker-rule") == marked_block(checker, "checker-rule")


def test_reviewer_does_not_raise_a_refused_break_again() -> None:
    _, body = read_agent("surface-reviewer")
    assert "`plan-change-refused`" in section(body, "What you read")
    assert "never raise it again as a break" in section(body, "Classifying a finding")


def test_reviewer_reads_and_never_runs_a_command_of_its_own() -> None:
    """A probe like `python3 -c` is refused by the permission rules, once per scenario (trial)."""
    _, body = read_agent("surface-reviewer")
    rule = next(line for line in body.splitlines() if line.startswith("You judge by reading"))
    assert "the gate results already recorded" in rule
    assert "You run no command of your own to check behavior" in rule
    assert "no `python3 -c`" in rule
    assert "Your commands are the state script and read-only git" in rule
    assert "raise it as a finding that names the command to run and what it must show" in rule
    # No other line of the prompt sends the reviewer to run code.
    others = body.replace(rule, "")
    assert "python3" not in others
    assert "pytest" not in others


# The form of a blueprint: a fixed frame, a body cut for the feature, as long as it needs.


def test_extractor_writes_a_blueprint_as_long_as_the_feature_needs() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    assert "The blueprint is as long as the feature needs, and no longer" in writing
    assert "a small change gets a short page" in writing
    assert "No section and no diagram is written for its own sake" in writing
    assert "each filled in" not in writing


def test_extractor_frames_the_blueprint_with_sections_that_carry_no_number() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    lines = writing.splitlines()
    for heading in (*BLUEPRINT_OPENING, BLUEPRINT_CLOSING):
        assert any(line.startswith(f"- {heading}") for line in lines), heading
    assert "It opens with three sections, in this order" in writing
    assert "It closes with one" in writing
    assert "No heading carries a number" in writing
    assert "a section is cited by its title, which an amendment does not move" in writing
    assert "keeps its number" not in writing


def test_extractor_cuts_the_body_by_what_the_developer_decides_separately() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    assert "by what the developer has to decide separately" in writing
    assert "never by the slices of the plan nor by the layout of the code" in writing
    assert "Take the first cut that fits" in writing
    cuts = [line for line in writing.splitlines() if re.match(r"[1-5]\. ", line)]
    assert [line.split(":", 1)[0] for line in cuts] == [
        "1. One behavior, a small change",
        "2. Several flows or visible behaviors, largely independent",
        "3. One flow that crosses several components with distinct responsibilities",
        "4. A feature that a few trade-offs dominate, a migration or a policy for instance",
        "5. Otherwise",
    ]
    assert "Title each section in the words of the feature, not of the method" in writing
    assert "Say a fact once" in writing


def test_extractor_says_a_fact_once_on_the_whole_page_and_shows_behavior_not_code() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    # The criteria state the rules: the body, the scope and the sensitive zones do not tell them
    # again, so the developer skips nothing of the page they approve.
    said = [
        "A fact is said once in prose on the whole page, the frame included",
        "the body shows what no criterion states",
        "The scope says what is left out: what is done stands in the criteria and in the body",
        "point to the criterion or the section that holds its rule",
    ]
    positions = [writing.index(sentence) for sentence in said]
    assert positions == sorted(positions)
    assert "names a criterion instead of saying it again" in writing
    # What must not be lost to brevity: the frame, a diagram, what stands nowhere else.
    assert "and a diagram may draw what the prose says" in writing
    assert "The acceptance criteria state the rules, carried whole" in writing
    assert "and say in full only what stands nowhere else" in writing
    always = "The statement of the critical zones and the closing line are always written"
    assert always in writing
    assert "shown on the page, by a criterion or in the body" in writing
    # Behavior, not code: what is seen from outside stays, what only the code sees goes.
    assert "It shows behavior, which the developer decides, not code" in writing
    assert "What a user, a file or another program sees stays on the page" in writing
    assert "which component calls which" in writing
    assert "What only the code sees stays in the plan" in writing
    template = Path(__file__).resolve().parents[2] / "skills/surface-plan/templates/blueprint.md"
    form = template.read_text(encoding="utf-8")
    assert "A fact is said once in prose on the whole page" in form
    assert "What it does stands in the criteria and in the body" in form
    assert "that no criterion states, as behavior and not as code" in form


def test_extractor_keeps_the_cut_of_the_previous_revision() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    kept = (
        "When `blueprint.md` already exists, read it before you write: keep its cut and its titles"
    )
    assert kept in writing
    assert (
        "Cut it again only when the developer asked for another cut, in `interview.md`" in writing
    )
    assert "or when the plan no longer fits the one it has" in writing
    assert "the cut you chose and why" in section(body, "What you return")


def test_extractor_goes_through_the_aspects_and_names_those_the_plan_leaves_alone() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    assert f"five aspects must not be left in the dark: {', '.join(BLUEPRINT_ASPECTS)}" in writing
    named = "one closing line that names every aspect the plan leaves alone, as the template shows"
    assert named in writing
    assert "There is no closing line when the plan changes all five" in writing
    assert "the aspects its closing line names" in section(body, "What you return")


def test_extractor_draws_a_diagram_when_prose_would_flatten_a_shape() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    rule = "Draw a mermaid diagram when what you describe has a shape that prose flattens"
    assert f"{rule}: several things in relation, an order between several actors" in writing
    assert "states and their transitions, a path that forks more than once." in writing
    assert "the existing elements it attaches to, marked as existing" in writing
    assert "A diagram may say again what the prose says" in writing
    # A chain with a single fork is no shape: one sentence says it, as it says a chain with none.
    none = "Do not draw one for a single fact, a list, a chain with no branch, or a chain with a"
    assert f"{none} single fork: a sentence says it better" in writing
    assert "a path that branches" not in writing
    assert "Never to fill a section" in writing
    assert "wherever one applies" not in body
    assert "only when it shows what the prose" not in body


def test_extractor_never_says_how_the_commits_of_the_work_are_written_or_signed() -> None:
    _, body = read_agent("surface-extractor")
    writing = section(body, "What you write")
    # A commit is written after the blueprint is frozen, by an agent that follows the conventions
    # of the repository: a page that promised its message or its author would be made false by it.
    never = "The blueprint never shows the slices nor the distribution of tests"
    rule = f"Nor does it say how the commits of the work are {COMMIT_FORM}"
    assert writing.index(never) < writing.index(rule)
    sentence = writing[writing.index(rule) :].split(". ", 1)[0]
    assert "the rest follows the conventions of the repository" in sentence
    assert "in the frozen contract a commit written another way would become a break" in sentence
    # What must not be lost with it: what the developer asked of the commits, and what is no
    # matter of how a commit is written, the branch the work lands on or what a push sets off.
    assert sentence.startswith(f"{rule}, {BLUEPRINT_ON_THE_COMMITS}: ")
    assert "branch" not in sentence
    assert "push" not in sentence


def test_checker_never_counts_a_cut_a_short_section_or_the_absence_of_a_diagram() -> None:
    _, body = read_agent("surface-checker")
    counting = section(body, "What counts as an omission")
    assert "The cut, the titles and the order of its sections are never an omission" in counting
    assert "neither is a short section or the absence of a diagram" in counting
    assert "only what the blueprint does not show counts" in counting
    assert f"five aspects must not be left in the dark: {', '.join(BLUEPRINT_ASPECTS)}" in counting
    assert "An aspect the closing line names while the plan changes it is an omission" in counting
    # A rule a criterion states is not told again in the body: the page shows it all the same.
    shown = (
        "neither shown on the page, by a criterion or in the body, nor named by the closing line"
    )
    assert shown in counting
    # The rule shared with the reviewer's amendment check stays as it was.
    rule = marked_block(counting, "checker-rule").lower()
    assert "closing line" not in rule
    assert "diagram" not in rule


# The critical zones: named in the sensitive zones of the blueprint, their changed files listed at
# conformity.


def test_extractor_opens_the_sensitive_zones_with_the_critical_zones_the_plan_touches() -> None:
    _, body = read_agent("surface-extractor")
    zones = next(line for line in body.splitlines() if line.startswith(f"- {BLUEPRINT_CLOSING}"))
    assert f"first {CRITICAL_ZONES_OF_THE_PLAN}, named as they name it" in zones
    assert f"or the statement that {TOUCHES_NONE}" in zones
    assert "then what the developer would not see go by" in zones
    assert "what the developer still reads themselves once the work is conformant" in body


def test_checker_counts_a_touched_critical_zone_missing_from_the_sensitive_zones() -> None:
    _, body = read_agent("surface-checker")
    counting = section(body, "What counts as an omission")
    assert f"names {CRITICAL_ZONES_OF_THE_PLAN}, or says that {TOUCHES_NONE}" in counting
    assert f"{UNNAMED_ZONE}, even when another section shows the change" in counting
    assert "says none while the plan touches one" in counting
    # The rule shared with the reviewer's amendment check stays as it was.
    assert "sensitive zones" not in marked_block(counting, "checker-rule").lower()


def test_reviewer_lists_the_changed_files_of_the_critical_zones_in_a_block() -> None:
    _, body = read_agent("surface-reviewer")
    writing = section(body, "What you write in a review")
    assert f"When you write `conformity.md`, end it with {CRITICAL_FILES_OF_THE_BRANCH}" in writing
    assert "the developer reads their code themselves" in writing
    assert "the state script shows them in the pull request description" in writing
    assert "Which files a zone covers is your reading" in writing
    assert f"keeps its `{CRITICAL_FILES_TAG}` tag in any language" in writing
    assert "one path per line from the root of the repository" in writing
    assert "a file the branch deleted included" in writing
    assert "Leave the block out when the branch changed no such file" in writing
    assert "or when the repository declares no critical zone" in writing
    refusal = "The script refuses `conformant` on a second block, an unclosed one, or a path"
    assert f"{refusal} the branch did not change" in writing


def test_the_block_the_reviewer_is_shown_is_one_the_script_reads() -> None:
    _, body = read_agent("surface-reviewer")
    assert parse_critical_files(body) == ("<path>",)


def test_reviewer_is_launched_for_three_things() -> None:
    fields, body = read_agent("surface-reviewer")
    first, second, third = REVIEWER_MODES
    assert f"and the mode: {first}, {second}, or {third}." in body
    assert "corrects a list of critical files the state script refused" in fields["description"]
    returned = section(body, "What you return")
    for mode in ("a review", "a suspected break", REFUSED_LIST):
        assert f"- {mode}: " in returned


def test_reviewer_corrects_a_refused_list_and_nothing_else() -> None:
    _, body = read_agent("surface-reviewer")
    correcting = section(body, f"What you correct on {REFUSED_LIST}")
    assert "The state script refused `conformant`" in correcting
    assert f"the `{CRITICAL_FILES_TAG}` block of `conformity.md` is malformed" in correcting
    assert "or names a file the branch did not change" in correcting
    assert "The reason is the one your mandate gives" in correcting
    assert "Correct that block and nothing else, in that file or anywhere" in correcting
    assert "you judge nothing again, you write no report" in correcting
    assert "every other line of `conformity.md` stays as it is" in correcting
    assert f"The block lists {CRITICAL_FILES_OF_THE_BRANCH}" in correcting
    assert "`<base>` being the base commit of your mandate" in correcting
    assert "Remove the block when the branch changed no such file" in correcting
    assert f"- {REFUSED_LIST}: `corrected`" in section(body, "What you return")


def test_no_other_prompt_writes_or_takes_up_the_critical_files_block() -> None:
    for path in prompt_files():
        if path.stem != "surface-reviewer":
            assert f"```{CRITICAL_FILES_TAG}" not in path.read_text(encoding="utf-8"), path


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
        ("surface-extractor", "`blueprint.md` in the plan folder, and nothing else"),
        ("surface-checker", "One report, and nothing else"),
        ("surface-reviewer", "you write your reports"),
    ],
)
def test_judgment_roles_write_only_their_own_files(name: str, writes: str) -> None:
    _, body = read_agent(name)
    assert writes in body
    assert "journal.jsonl`" in body


# The language of what the roles write: the one `exploration.md` names, never the specs'.


@pytest.mark.parametrize(
    ("name", "writes"),
    [
        ("surface-extractor", "Write in"),
        ("surface-checker", "Write it in"),
        ("surface-reviewer", "Write in"),
        ("surface-executor", "amend `plan.md` where it describes the slice, in"),
    ],
)
def test_every_role_writes_in_the_language_exploration_names(name: str, writes: str) -> None:
    _, body = read_agent(name)
    assert f"{writes} {DOCUMENTS_LANGUAGE}" in body


@pytest.mark.parametrize("name", ["surface-extractor", "surface-checker"])
def test_roles_that_read_the_developers_words_work_from_the_translation(name: str) -> None:
    _, body = read_agent(name)
    reading = section(body, "What you read")
    assert "Where `specs.md` or `interview.md` quotes the developer in another language" in reading
    assert WORK_FROM_TRANSLATION in reading


def test_reviewer_reads_the_language_in_exploration() -> None:
    _, body = read_agent("surface-reviewer")
    assert "`exploration.md`, in its repository rules" in section(body, "What you read")


def test_executor_never_modifies_the_blueprint() -> None:
    _, body = read_agent("surface-executor")
    never = section(body, "What you never do")
    assert "Modify `blueprint.md`" in never
    assert "in the foreground, with a timeout" in never


def test_executor_never_edits_a_report_it_does_not_own_and_stops_on_one() -> None:
    _, body = read_agent("surface-executor")
    never = section(body, "What you never do")
    rule = next(line for line in never.splitlines() if "Edit, rewrite or delete a report" in line)
    assert [path for path in CHAIN_REPORTS if f"`{path}`" not in rule] == []
    assert "stop there" in rule
    assert "`a report fails a gate`" in section(body, "What you return")


# Commands run from the root of the repository: a `cd` moves the shell the dispatcher and its
# agents share, and a `cd` followed by git stops for an approval nobody gives, as does `git -C`,
# which the reviewer reached for in the trial.

_CODE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
_CD = re.compile(r"(?:^|[\s;&|(!])cd |\bgit -C ")


def _prompt_id(path: Path) -> str:
    return path.parent.name if path.name == "SKILL.md" else path.stem


@pytest.mark.parametrize("path", prompt_files(), ids=_prompt_id)
def test_no_command_of_a_prompt_changes_directory(path: Path) -> None:
    code = _CODE.findall(path.read_text(encoding="utf-8"))
    assert [span for span in code if _CD.search(span.strip("`"))] == []


def test_the_cd_check_sees_a_cd_in_code() -> None:
    for text in (
        "`cd docs/plans/x && git log`",
        "```sh\ngit status; cd app\n```",
        "`git -C /some/repo log`",
    ):
        assert [span for span in _CODE.findall(text) if _CD.search(span.strip("`"))]
    for text in ("never `cd`", "nor `git -C`"):
        assert not [span for span in _CODE.findall(text) if _CD.search(span.strip("`"))]


@pytest.mark.parametrize("path", prompt_files(), ids=_prompt_id)
def test_every_prompt_that_runs_commands_stays_at_the_root(path: Path) -> None:
    fields, body = split_agent(path.read_text(encoding="utf-8"))
    runs_bash = "Bash" in fields.get("tools", "") or "Bash(" in fields.get("allowed-tools", "")
    if runs_bash:
        assert "from the root of the repository, with paths from there" in body
        assert "`cd`" in body
        assert "`git -C`" in body


# How an agent writes its other commands, and the tool it changes a file with, are its own
# judgment: a rule that general is not the chain's, and what stops for an approval is the
# permission mode's call (ADR 0032).


@pytest.mark.parametrize("path", prompt_files(), ids=_prompt_id)
def test_no_prompt_says_how_an_agent_writes_a_command(path: Path) -> None:
    body = path.read_text(encoding="utf-8")
    for rule in ("plain command", "here-document", "`find -exec`", "Write and edit files with"):
        assert rule not in body


def test_executor_commits_each_slice_with_its_journal_line_and_amendment() -> None:
    _, body = read_agent("surface-executor")
    slice_steps = section(body, "A slice")
    assert "One commit for the slice" in slice_steps
    assert "`plan.md` if amended, and `journal.jsonl`" in slice_steps
    assert "suspected break" in slice_steps
    assert "Leave your work uncommitted" in slice_steps
    assert "continue them or undo them" in section(body, "Uncommitted work")


def test_executor_commits_by_pathspec_never_the_whole_tree() -> None:
    _, body = read_agent("surface-executor")
    assert "One commit for the slice, by pathspec" in section(body, "A slice")
    assert "Never `git add -A` nor `git add .`" in section(body, "A slice")
    assert "one commit, by pathspec" in section(body, "A fix")


def test_reviewer_reads_the_alarm_of_the_script_instead_of_hashing() -> None:
    _, body = read_agent("surface-reviewer")
    reads = section(body, "What you read")
    assert "`alarms` of `surface-status show <plan> --json`" in reads
    assert "Never hash it yourself" in reads


def test_extractor_names_no_identifier_of_the_plan_or_the_interview() -> None:
    _, body = read_agent("surface-extractor")
    assert "cross-reference the blueprint and the plan, nor the interview" in body


# Calls of the state script, by the agents and the skills: only subcommands, events and fields
# its parser accepts.


@pytest.mark.parametrize(("name", "call"), [_call_param(name, call) for name, call in _all_calls()])
def test_prompts_call_the_script_only_as_its_parser_accepts(name: str, call: str) -> None:
    del name  # in the test id
    try:
        build_parser().parse_args(call_arguments(call))
    except UsageError as error:
        pytest.fail(f"`{call}` does not parse: {error}")


def test_every_prompt_that_refreshes_the_pr_says_pr_body_takes_no_argument() -> None:
    """The dispatcher passed the plan to `pr-body` like to every other call (trial).

    The pipe then hands `gh pr edit --body-file -` an empty description.
    """
    callers = {name for name, call in _all_calls() if call_arguments(call)[0] == "pr-body"}
    assert callers == {"surface-execute", "surface-plan", "surface-status"}
    for path in prompt_files():
        if _prompt_id(path) in callers:
            text = path.read_text(encoding="utf-8")
            assert "(it takes no argument, since it describes every plan of the branch)" in text
    for name, call in _all_calls():
        if call_arguments(call)[0] == "pr-body":
            assert list(call_arguments(call)) == ["pr-body"], f"{name}: {call}"


def test_the_calls_are_found() -> None:
    callers = {name for name, _ in _all_calls()}
    assert callers >= {"surface-executor", "surface-reviewer", "surface-plan"}
    called = {tuple(call_arguments(call)[:3:2]) for _, call in _all_calls()}
    assert {("record", "slice-done"), ("record", "plan-amended"), ("record", "fix-done")} <= called
    assert {call_arguments(call)[0] for _, call in _all_calls()} >= {"show", "record", "gate"}
