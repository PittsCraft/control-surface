"""The stand-in `gh` of the test image, run as a script (tests/e2e/toy/gh_stand_in.py).

No container and no session: each test runs the script in a temporary repository that has a bare
remote, as the toy project and the host of the evaluations do, and reads what it printed, what it
keeps and what it recorded. The messages held here are those of `gh` 2.78.0 without a terminal.
"""

import fcntl
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import gh_stand_in
import pytest
import toy

BRANCH = "feat/csv-export"
TITLE = "Export the shelf as CSV"
BODY = "## Plans on this branch\n\n- `2026-01-15-csv-export`: awaiting approval\n"
ADDRESS = "https://github.com/stand-in/shelf/pull/1"
NO_PULL = f'no pull requests found for branch "{BRANCH}"\n'
READY = '\N{CHECK MARK} Pull request stand-in/shelf#1 is marked as "ready for review"\n'
SCRIPT = [sys.executable, gh_stand_in.__file__]
PATIENCE = 120  # seconds a call may take on a loaded machine before a test gives up on it


@dataclass(frozen=True, slots=True)
class Answer:
    code: int
    out: str
    err: str


def gh(folder: Path, *args: str, stdin: str = "", ceiling: Path | None = None) -> Answer:
    """Run the stand-in in a folder, as a session would run `gh` there.

    `ceiling` is a folder git must not look above for a repository: a test that runs outside
    any must not find the one the temporary folders happen to live in.
    """
    done = subprocess.run(
        [*SCRIPT, *args],
        cwd=folder,
        input=stdin,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=PATIENCE,
        env={**os.environ, "GIT_CEILING_DIRECTORIES": "" if ceiling is None else str(ceiling)},
    )
    return Answer(done.returncode, done.stdout, done.stderr)


def repository(folder: Path) -> Path:
    """Make a repository with one commit on its main branch."""
    folder.mkdir()
    toy.git(folder, "init", "--quiet", "--initial-branch=main")
    for key, value in (
        ("user.name", "Toy Developer"),
        ("user.email", "developer@example.com"),
        ("commit.gpgsign", "false"),
    ):
        toy.git(folder, "config", key, value)
    toy.write(folder, {"README.md": "# shelf\n"})
    toy.commit(folder, "shelf: start", ["README.md"])
    return folder


def branch(repo: Path, name: str) -> None:
    """Start a branch from main, one commit ahead, and push it."""
    toy.git(repo, "switch", "--quiet", "--create", name, "main")
    path = f"docs/{name.replace('/', '-')}.md"
    toy.write(repo, {path: "# Plan\n"})
    toy.commit(repo, "plan: draft", [path])
    toy.git(repo, "push", "--quiet", "--set-upstream", "origin", name)


@pytest.fixture(scope="module")
def pushed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build once the folder every test starts from a copy of: a repository and its remote."""
    folder = tmp_path_factory.mktemp("pushed")
    repo = repository(folder / "shelf")
    toy.git(folder, "init", "--quiet", "--bare", "--initial-branch=main", "origin.git")
    # A path from the repository, so that a copy of the folder pushes to its own remote.
    toy.git(repo, "remote", "add", "origin", "../origin.git")
    toy.git(repo, "push", "--quiet", "--set-upstream", "origin", "main")
    toy.git(repo, "remote", "set-head", "origin", "main")
    branch(repo, BRANCH)
    return folder


@pytest.fixture
def project(tmp_path: Path, pushed: Path) -> Path:
    """Give a test its repository: on a feature branch, pushed to its bare remote."""
    shutil.copytree(pushed, tmp_path, dirs_exist_ok=True)
    return tmp_path / "shelf"


def draft(repo: Path) -> Answer:
    return gh(repo, "pr", "create", "--draft", "--title", TITLE, "--body", BODY)


# Opening a pull request.


def test_a_draft_is_opened_for_the_pushed_branch_and_its_address_printed(project: Path) -> None:
    assert draft(project) == Answer(0, f"{ADDRESS}\n", "")
    (pull,) = gh_stand_in.pulls(project)
    assert (pull.number, pull.head, pull.base) == (1, BRANCH, "main")
    assert (pull.title, pull.body, pull.state) == (TITLE, BODY, "OPEN")
    assert pull.draft
    assert gh_stand_in.pull_of(project, BRANCH) == pull
    assert gh_stand_in.pull_of(project, "main") is None


def test_a_pull_request_opened_without_the_flag_is_not_a_draft(project: Path) -> None:
    assert gh(project, "pr", "create", "-t", TITLE, "-b", BODY).code == 0
    assert not gh_stand_in.pulls(project)[0].draft


def test_short_flags_written_together_are_read_one_by_one(project: Path) -> None:
    assert gh(project, "pr", "create", "-dt", TITLE, "-b", BODY).code == 0
    (pull,) = gh_stand_in.pulls(project)
    assert (pull.draft, pull.title, pull.body) == (True, TITLE, BODY)
    assert gh(project, "pr", "list", "-d=false", "--json", "number").out == "[]\n"


def test_a_second_pull_request_for_the_branch_is_refused(project: Path) -> None:
    draft(project)
    already = f'a pull request for branch "{BRANCH}" into branch "main" already exists:\n'
    assert draft(project) == Answer(1, "", f"{already}{ADDRESS}\n")
    assert len(gh_stand_in.pulls(project)) == 1
    # Another branch has its own, under the next number.
    branch(project, "feat/isbn")
    assert draft(project).out == "https://github.com/stand-in/shelf/pull/2\n"


def test_a_branch_the_remote_does_not_hold_as_it_is_opens_nothing(project: Path) -> None:
    aborted = "aborted: you must first push the current branch to a remote, or use the --head flag"
    toy.write(project, {"docs/more.md": "# More\n"})
    toy.commit(project, "plan: more", ["docs/more.md"])
    assert draft(project) == Answer(1, "", f"{aborted}\n")
    toy.git(project, "switch", "--quiet", "--create", "feat/never-pushed")
    assert draft(project) == Answer(1, "", f"{aborted}\n")
    assert gh_stand_in.pulls(project) == []
    toy.git(project, "push", "--quiet", "--set-upstream", "origin", "feat/never-pushed")
    assert draft(project).code == 0


def test_a_branch_with_nothing_to_merge_opens_nothing(project: Path) -> None:
    toy.git(project, "switch", "--quiet", "main")
    refusal = "pull request create failed: GraphQL: No commits between main and main"
    assert draft(project) == Answer(1, "", f"{refusal} (createPullRequest)\n")


def test_a_head_named_by_its_flag_is_opened_from_another_branch(project: Path) -> None:
    toy.git(project, "switch", "--quiet", "main")
    opening = ("pr", "create", "--title", TITLE, "--body", BODY, "--head")
    nowhere = gh(project, *opening, "feat/nowhere")
    assert (nowhere.code, nowhere.out) == (1, "")
    assert "Head ref must be a branch (createPullRequest)" in nowhere.err
    assert gh(project, *opening, BRANCH) == Answer(0, f"{ADDRESS}\n", "")
    assert gh_stand_in.pulls(project)[0].head == BRANCH


def test_a_title_and_a_description_are_required_without_a_terminal(project: Path) -> None:
    required = (
        "must provide `--title` and `--body` (or `--fill` or `fill-first` or `--fillverbose`)"
        " when not running interactively\n"
    )
    assert gh(project, "pr", "create", "--draft") == Answer(1, "", required)
    assert gh(project, "pr", "create", "--draft", "--title", TITLE) == Answer(1, "", required)
    assert gh(project, "pr", "create", "--draft", "--body", BODY) == Answer(1, "", required)
    blank = gh(project, "pr", "create", "--title", " ", "--body", BODY)
    assert blank == Answer(1, "", "pull request title must not be blank\n")
    assert gh_stand_in.pulls(project) == []


def test_uncommitted_changes_are_warned_of_and_do_not_stop_the_opening(project: Path) -> None:
    toy.write(project, {"notes.txt": "a note\n"})
    assert draft(project) == Answer(0, f"{ADDRESS}\n", "Warning: 1 uncommitted change\n")


# The description: opened with, then replaced.


def test_the_description_comes_from_a_flag_a_file_or_the_standard_input(project: Path) -> None:
    (project.parent / "body.md").write_text("From a file.\n", encoding="utf-8")
    opened = gh(project, "pr", "create", "--draft", "--title", TITLE, "--body-file", "../body.md")
    assert opened.code == 0
    assert gh_stand_in.pulls(project)[0].body == "From a file.\n"
    assert gh(project, "pr", "edit", "--body", "From the flag.") == Answer(0, f"{ADDRESS}\n", "")
    assert gh_stand_in.pulls(project)[0].body == "From the flag."
    # What the chain does at every stop: the description on the standard input.
    refreshed = gh(project, "pr", "edit", "--body-file", "-", stdin=BODY)
    assert refreshed == Answer(0, f"{ADDRESS}\n", "")
    (pull,) = gh_stand_in.pulls(project)
    assert (pull.body, pull.title, pull.draft) == (BODY, TITLE, True)
    missing = gh(project, "pr", "edit", "--body-file", "nowhere.md")
    assert missing == Answer(1, "", "open nowhere.md: no such file or directory\n")
    assert gh_stand_in.pulls(project)[0].body == BODY


def test_an_edit_fails_when_the_branch_has_no_pull_request(project: Path) -> None:
    assert gh(project, "pr", "edit", "--body", BODY) == Answer(1, "", NO_PULL)
    assert gh(project, "pr", "edit", "--body-file", "-", stdin=BODY) == Answer(1, "", NO_PULL)
    assert gh_stand_in.pulls(project) == []
    # The record still holds the description the call came with.
    last = gh_stand_in.calls(project)[-1]
    assert (last.stdin, last.body, last.pull, last.exit_code) == (BODY, BODY, None, 1)
    assert last.played


def test_an_edit_names_a_pull_request_by_number_address_or_branch(project: Path) -> None:
    draft(project)
    toy.git(project, "switch", "--quiet", "main")
    assert gh(project, "pr", "edit", "--body", "x") == Answer(
        1, "", 'no pull requests found for branch "main"\n'
    )
    for name in ("1", "#1", ADDRESS, BRANCH):
        assert gh(project, "pr", "edit", name, "--body", name).out == f"{ADDRESS}\n"
        assert gh_stand_in.pulls(project)[0].body == name
    unknown = "GraphQL: Could not resolve to a PullRequest with the number of 7."
    assert gh(project, "pr", "edit", "7", "--title", "x") == Answer(
        1, "", f"{unknown} (repository.pullRequest)\n"
    )


def test_an_edit_with_nothing_to_change_or_two_descriptions_is_refused(project: Path) -> None:
    draft(project)
    nothing = gh(project, "pr", "edit")
    assert nothing.code == 1
    assert nothing.err.endswith("required when not running interactively\n")
    both = gh(project, "pr", "edit", "--body", "x", "--body-file", "-", stdin="y")
    assert both == Answer(1, "", "specify only one of `--body` or `--body-file`\n")
    assert gh(project, "pr", "edit", "--title") == Answer(
        1, "", "flag needs an argument: --title\n"
    )
    assert gh_stand_in.pulls(project)[0].body == BODY


def test_a_description_piped_from_another_call_does_not_hold_that_call_back(
    project: Path,
) -> None:
    draft(project)
    # As in `gh pr view ... | gh pr edit --body-file -`: the edit waits for its description
    # with nothing held, so the call that feeds it is answered.
    editing = subprocess.Popen(
        [*SCRIPT, "pr", "edit", "--body-file", "-"],
        cwd=project,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    viewed = gh(project, "pr", "view", "--json", "title", "--jq", ".title")
    out, err = editing.communicate(viewed.out, timeout=PATIENCE)
    assert viewed == Answer(0, f"{TITLE}\n", "")
    assert (editing.returncode, out, err) == (0, f"{ADDRESS}\n", "")
    assert gh_stand_in.pulls(project)[0].body == f"{TITLE}\n"


# Listing and viewing.


def test_the_list_answers_in_the_fields_asked(project: Path) -> None:
    team = ("pr", "list", "--state", "all", "--limit", "50", "--json", "headRefName,author")
    mine = ("pr", "list", "--state", "all", "--author", "@me", "--limit", "50", "--json")
    assert gh(project, *team) == Answer(0, "[]\n", "")
    draft(project)
    author = '{"id":"stand-in","is_bot":false,"login":"developer","name":"Developer"}'
    assert gh(project, *team).out == f'[{{"author":{author},"headRefName":"{BRANCH}"}}]\n'
    assert gh(project, *mine, "headRefName").out == f'[{{"headRefName":"{BRANCH}"}}]\n'
    assert gh(project, *mine, "headRefName", "--jq", ".[].headRefName").out == f"{BRANCH}\n"


def test_the_list_filters_by_state_branch_draft_author_and_limit(project: Path) -> None:
    draft(project)
    branch(project, "feat/isbn")
    gh(project, "pr", "create", "--title", "Export the ISBN", "--body", "")

    def numbers(*flags: str) -> list[int]:
        listed = gh(project, "pr", "list", *flags, "--json", "number")
        return [row["number"] for row in json.loads(listed.out)]

    assert numbers() == [2, 1]  # the last opened first
    assert numbers("--limit", "1") == [2]
    assert numbers("--head", BRANCH) == [1]
    assert numbers("--draft") == [1]
    assert numbers("--draft=false") == [2]
    assert numbers("--state", "merged") == []
    assert numbers("--author", "someone-else") == []
    assert numbers("-s", "all", "-A", "developer", "-B", "main", "-L", "5") == [2, 1]
    rows = gh(project, "pr", "list").out.splitlines()
    assert rows[0].split("\t")[:4] == ["2", "Export the ISBN", "feat/isbn", "OPEN"]
    assert rows[1].split("\t")[:4] == ["1", TITLE, BRANCH, "DRAFT"]
    state = 'invalid argument "bogus" for "-s, --state" flag: valid values are'
    assert gh(project, "pr", "list", "--state", "bogus") == Answer(
        1, "", f"{state} {{open|closed|merged|all}}\n"
    )
    assert gh(project, "pr", "list", "--limit", "0").err == "invalid value for --limit: 0\n"
    assert gh(project, "pr", "list", "--jq", ".") == Answer(
        1, "", "cannot use `--jq` without specifying `--json`\n"
    )
    fields = gh(project, "pr", "list", "--json")
    assert fields.code == 1
    assert fields.err.startswith(
        "Specify one or more comma-separated fields for `--json`:\n  author\n  baseRefName\n"
    )


def test_a_view_shows_the_pull_request_of_the_branch(project: Path) -> None:
    assert gh(project, "pr", "view") == Answer(1, "", NO_PULL)
    draft(project)
    shown = gh(project, "pr", "view")
    head, body = shown.out.split("--\n", 1)
    assert body == f"{BODY}\n"
    assert f"title:\t{TITLE}\nstate:\tDRAFT\nauthor:\tdeveloper\n" in head
    assert f"number:\t1\nurl:\t{ADDRESS}\n" in head
    asked = gh(project, "pr", "view", "--json", "number,isDraft,state,url,baseRefName")
    assert json.loads(asked.out) == {
        "number": 1,
        "isDraft": True,
        "state": "OPEN",
        "url": ADDRESS,
        "baseRefName": "main",
    }
    assert gh(project, "pr", "view", "1", "--json", "url,body", "-q", ".url").out == f"{ADDRESS}\n"
    assert gh(project, "pr", "view", "--json", "body", "--jq", ". | .body").out == f"{BODY}\n"


def test_without_a_branch_checked_out_a_pull_request_is_named_or_not_found(
    project: Path,
) -> None:
    draft(project)
    toy.git(project, "checkout", "--quiet", "--detach")
    assert gh(project, "pr", "view") == Answer(1, "", "failed to run git: not on any branch\n")
    assert gh(project, "pr", "view", "1", "--json", "number").out == '{"number":1}\n'


def test_the_repository_is_named_after_its_folder(project: Path) -> None:
    asked = gh(project, "repo", "view", "--json", "nameWithOwner,url,defaultBranchRef")
    assert json.loads(asked.out) == {
        "nameWithOwner": "stand-in/shelf",
        "url": "https://github.com/stand-in/shelf",
        "defaultBranchRef": {"name": "main"},
    }
    assert gh(project, "repo", "view").out == "name:\tstand-in/shelf\ndescription:\t\n"
    assert "Logged in to github.com account developer" in gh(project, "auth", "status").out


# Marking ready: the chain never does it, so the record says when a call did.


def test_marking_ready_is_played_and_recorded_as_such(project: Path) -> None:
    draft(project)
    assert gh(project, "pr", "ready") == Answer(0, "", READY)
    assert not gh_stand_in.pulls(project)[0].draft
    already = '! Pull request stand-in/shelf#1 is already "ready for review"\n'
    assert gh(project, "pr", "ready", "1") == Answer(0, "", already)
    undone = '\N{CHECK MARK} Pull request stand-in/shelf#1 is converted to "draft"\n'
    assert gh(project, "pr", "ready", "--undo") == Answer(0, "", undone)
    assert gh_stand_in.pulls(project)[0].draft
    assert gh(project, "pr", "ready", "--undo=true").code == 0
    marks = [call.marks_ready for call in gh_stand_in.calls(project)]
    assert marks == [False, True, True, False, False]


def test_a_call_that_marks_ready_is_recorded_even_when_it_reaches_nothing(project: Path) -> None:
    assert gh(project, "pr", "ready") == Answer(1, "", NO_PULL)
    assert gh(project, "pr", "ready", "--now").code == 1
    reached, unread = gh_stand_in.calls(project)
    assert reached.marks_ready
    assert (reached.command, reached.played, reached.exit_code) == ("pr ready", True, 1)
    # A call the stand-in could not even read asked for it all the same.
    assert (unread.marks_ready, unread.played) == (True, False)


# What the stand-in does not play, and what it records.


@pytest.mark.parametrize(
    ("args", "command"),
    [
        (("api", "user"), None),
        (("pr", "merge", "--squash"), None),
        (("issue", "list"), None),
        (("pr", "create", "--draft", "--fill"), "pr create"),
        (("pr", "edit", "--add-label", "plan"), "pr edit"),
        (("pr", "list", "--json", "number", "--jq", "map(.number)"), "pr list"),
        (("pr", "list", "--json", "number", "--jq", ".[].number.digits"), "pr list"),
        (("pr", "view", "--json", "comments"), "pr view"),
        (("repo", "view", "someone/else"), "repo view"),
    ],
)
def test_anything_else_is_refused_and_recorded_as_not_played(
    project: Path, args: tuple[str, ...], command: str | None
) -> None:
    draft(project)
    before = gh_stand_in.pulls(project)
    answer = gh(project, *args)
    assert (answer.code, answer.out) == (1, "")
    assert "not played here" in answer.err or answer.err.startswith("Unknown JSON field")
    call = gh_stand_in.calls(project)[-1]
    assert (call.argv, call.command, call.played) == (args, command, False)
    assert (call.exit_code, call.stderr) == (1, answer.err)
    assert gh_stand_in.pulls(project) == before


def test_a_field_the_stand_in_does_not_hold_is_answered_as_gh_names_an_unknown_one(
    project: Path,
) -> None:
    unknown = gh(project, "pr", "list", "--json", "headRefName,reviews")
    assert unknown.err.startswith('Unknown JSON field: "reviews"\nAvailable fields:\n  author\n')
    for field in gh_stand_in.PULL_FIELDS:
        assert f"\n  {field}\n" in unknown.err


def test_every_call_is_recorded_with_its_arguments_and_its_standard_input(project: Path) -> None:
    gh(project, "pr", "list", "--state", "all", "--json", "headRefName")
    gh(project, "pr", "create", "--draft", "--title", TITLE, "--body-file", "-", stdin=BODY)
    gh(project, "pr", "edit", "--body", "Refreshed.")
    listed, opened, edited = gh_stand_in.calls(project)
    assert listed.argv == ("pr", "list", "--state", "all", "--json", "headRefName")
    assert (listed.command, listed.stdin, listed.body, listed.pull) == ("pr list", None, None, None)
    assert (listed.branch, listed.exit_code, listed.stdout) == (BRANCH, 0, "[]\n")
    assert opened.argv == ("pr", "create", "--draft", "--title", TITLE, "--body-file", "-")
    assert (opened.command, opened.stdin, opened.body, opened.pull) == ("pr create", BODY, BODY, 1)
    assert opened.stdout == f"{ADDRESS}\n"
    assert (edited.command, edited.stdin, edited.body, edited.pull) == (
        "pr edit",
        None,
        "Refreshed.",
        1,
    )
    assert all(call.played and not call.marks_ready for call in (listed, opened, edited))
    assert listed.at <= opened.at <= edited.at
    # One line per call, each a JSON object of its own.
    lines = (gh_stand_in.store(project) / gh_stand_in.RECORD).read_text("utf-8").splitlines()
    assert [json.loads(line)["argv"][1] for line in lines] == ["list", "create", "edit"]


def test_a_line_cut_by_a_kill_costs_the_record_that_line_alone(project: Path) -> None:
    draft(project)
    record = gh_stand_in.store(project) / gh_stand_in.RECORD
    whole = record.read_text(encoding="utf-8")
    record.write_text(f'{whole}[1, 2]\n{{"v": 1, "at": "20', encoding="utf-8")
    assert [call.command for call in gh_stand_in.calls(project)] == ["pr create"]
    # The next call starts a line of its own, and is read.
    gh(project, "pr", "view")
    assert [call.command for call in gh_stand_in.calls(project)] == ["pr create", "pr view"]


def test_a_call_waits_while_another_holds_the_folder(project: Path) -> None:
    draft(project)
    with (gh_stand_in.store(project) / gh_stand_in.LOCK).open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        waiting = subprocess.Popen(
            [*SCRIPT, "pr", "edit", "--body", "Later."],
            cwd=project,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with pytest.raises(subprocess.TimeoutExpired):
            waiting.wait(timeout=2)
        assert gh_stand_in.pulls(project)[0].body == BODY
    assert waiting.wait(timeout=PATIENCE) == 0
    assert gh_stand_in.pulls(project)[0].body == "Later."


def test_calls_made_at_the_same_time_are_all_kept(project: Path) -> None:
    draft(project)
    bodies = [f"Description {number:02d}." for number in range(12)]

    def edit(body: str) -> Answer:
        return gh(project, "pr", "edit", "--body", body)

    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        answers = list(pool.map(edit, bodies))
    assert [answer.code for answer in answers] == [0] * len(bodies)
    edits = [str(call.body) for call in gh_stand_in.calls(project) if call.command == "pr edit"]
    assert sorted(edits) == bodies
    # The pull request holds the description of the call recorded last.
    assert gh_stand_in.pulls(project)[0].body == edits[-1]


# Where the record lives.


def test_each_repository_keeps_its_own_pull_requests_and_its_own_record(project: Path) -> None:
    # Two projects of one container, here with the same remote: nothing is shared between them.
    other = repository(project.parent / "lending")
    toy.git(other, "remote", "add", "origin", "../origin.git")
    draft(project)
    assert gh(other, "pr", "list", "--json", "number").out == "[]\n"
    assert [call.command for call in gh_stand_in.calls(project)] == ["pr create"]
    assert [call.command for call in gh_stand_in.calls(other)] == ["pr list"]
    assert gh_stand_in.pulls(other) == []


def test_the_record_stays_out_of_the_work_tree(project: Path) -> None:
    draft(project)
    gh(project, "pr", "view")
    assert toy.git(project, "status", "--porcelain") == ""
    assert gh_stand_in.store(project) == project / ".git" / "gh-stand-in"
    assert (gh_stand_in.store(project) / "calls.jsonl").is_file()
    assert (gh_stand_in.store(project) / "pulls.json").is_file()


def test_a_call_from_a_subfolder_reaches_the_pull_requests_of_the_repository(
    project: Path,
) -> None:
    draft(project)
    viewed = gh(project / "docs", "pr", "view", "--json", "number")
    assert viewed == Answer(0, '{"number":1}\n', "")
    assert len(gh_stand_in.calls(project)) == 2


def test_a_repository_without_a_remote_has_no_github(tmp_path: Path) -> None:
    alone = repository(tmp_path / "alone")
    for args in (("pr", "list"), ("pr", "view"), ("pr", "edit", "--body", "x"), ("repo", "view")):
        assert gh(alone, *args) == Answer(1, "", "no git remotes found\n")
    opened = gh(alone, "pr", "create", "--draft", "--title", TITLE, "--body", BODY)
    assert opened == Answer(1, "", "no git remotes found\n")
    # Refused as `gh` does, and recorded all the same: the git directory is always there.
    assert [call.exit_code for call in gh_stand_in.calls(alone)] == [1] * 5


def test_outside_a_repository_nothing_is_played_but_the_version_and_the_help(
    tmp_path: Path,
) -> None:
    above = tmp_path.parent
    listed = gh(tmp_path, "pr", "list", ceiling=above)
    assert (listed.code, listed.out) == (1, "")
    assert listed.err.startswith("failed to run git: fatal: not a git repository")
    version = gh(tmp_path, "--version", ceiling=above)
    assert version == Answer(0, "gh version 2.78.0 (stand-in)\n", "")
    told = gh(tmp_path, "pr", "create", "--help", ceiling=above)
    assert told.code == 0
    for command in ("pr create", "pr edit", "pr list", "pr view", "pr ready", "repo view"):
        assert f"  gh {command}" in told.out
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="the administrator writes where nobody else may")
def test_where_nothing_can_be_kept_a_call_says_so_in_one_line(project: Path) -> None:
    git_directory = project / ".git"
    git_directory.chmod(0o555)
    try:
        listed = gh(project, "pr", "list")
        version = gh(project, "--version")
    finally:
        git_directory.chmod(0o755)
    assert (listed.code, listed.out) == (1, "")
    assert listed.err.startswith("gh stand-in: nothing can be kept in ")
    assert listed.err.count("\n") == 1
    assert version == Answer(0, "gh version 2.78.0 (stand-in)\n", "")
    assert gh_stand_in.calls(project) == []


# The states a harness prepares.


def test_a_pull_request_opened_by_a_harness_is_kept_without_a_call(project: Path) -> None:
    opened = gh_stand_in.open_pull(
        project, head=BRANCH, base="main", title=TITLE, body=BODY, draft=True
    )
    assert gh_stand_in.pulls(project) == [opened]
    assert gh_stand_in.calls(project) == []
    # A session then meets it as one `gh` opened.
    assert gh(project, "pr", "view", "--json", "isDraft,body").out == (
        json.dumps({"body": BODY, "isDraft": True}, separators=(",", ":")) + "\n"
    )
    assert draft(project).code == 1


def test_a_plan_the_toy_prepares_has_the_draft_its_planning_would_have_opened(
    tmp_path: Path,
) -> None:
    project = toy.build(toy.State.AWAITING, tmp_path)
    pull = gh_stand_in.pull_of(project, toy.BRANCH)
    assert pull is not None
    assert (pull.draft, pull.base, pull.title) == (True, "main", toy.PULL_TITLE)
    assert pull.body == toy.pr_body(project)
    assert "awaiting-approval" in pull.body
    assert gh_stand_in.calls(project) == []
    assert toy.git(project, "status", "--porcelain") == ""


def test_a_loop_the_toy_prepares_left_the_description_of_the_draft(tmp_path: Path) -> None:
    project = toy.build(toy.State.DONE, tmp_path)
    pull = gh_stand_in.pull_of(project, toy.BRANCH)
    assert pull is not None
    assert pull.draft
    # No stop refreshed it since the hand over: it still tells the plan as awaiting approval.
    assert "awaiting-approval" in pull.body
    assert pull.body != toy.pr_body(project)
