"""End to end: the chain on the toy project, headless, from prepared states (ADR 0025).

Billed and slow: run on demand only, with `scripts/gate.sh e2e`, never in CI. The sessions bypass
permissions, so they run in the container of `tests/e2e/Dockerfile` (ADR 0025). Each scenario
keeps the stream of its sessions under `logs/` next to the toy project, in pytest's temporary
folder (`--basetemp` chooses it). Where a scenario needs the developer's answers, they are
written here and given one session each, with `--resume`: no model plays the developer, which is
what the evaluations do (ADR 0036). See `tests/e2e/README.md`.
"""

import json
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gh_stand_in
import pytest
import toy

WATCH = 0.5  # seconds between two looks at a session to kill at a chosen moment
MAX_REPLIES = 12  # what the developer says to one conversation, at most
# Every question of the chain is lettered and carries a recommendation: this reply answers any.
RECOMMENDED = "I take the option you recommend."
NEED = (
    "Export the shelf as CSV for the bookshop: title, author and year, sorted by author then title."
)
AMENDMENT = "Put the year first: year, title, author."


def plan_of(project: Path) -> str:
    """Name the plan folder of a project: the prepared one, else the one a session opened."""
    prepared = toy.plan_name()
    if (project / "docs" / "plans" / prepared).is_dir():
        return prepared
    (opened,) = project.glob("docs/plans/*/journal.jsonl")
    return opened.parent.name


def document(project: Path, name: str) -> Path:
    return project / "docs" / "plans" / plan_of(project) / name


def journal(project: Path, plan: str | None = None) -> list[dict[str, Any]]:
    path = project / "docs" / "plans" / (plan or plan_of(project)) / "journal.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def events(project: Path, plan: str | None = None) -> list[str]:
    return [line["event"] for line in journal(project, plan)]


def state(project: Path) -> str:
    shown = toy.show(project, f"docs/plans/{plan_of(project)}")
    return str(shown["state"])


def dirty(project: Path, *paths: str) -> bool:
    # Without the lock a status takes on the index: a session at work there would find it held.
    status = toy.git(project, "--no-optional-locks", "status", "--porcelain", "--", *paths)
    return bool(status.strip())


def pushed(project: Path) -> bool:
    """Whether the bare remote holds the branch at its last commit."""
    branch = toy.git(project, "branch", "--show-current").strip()
    held = toy.git(project, "ls-remote", "origin", f"refs/heads/{branch}").split()
    return bool(held) and held[0] == toy.git(project, "rev-parse", "HEAD").strip()


def on_the_remote(project: Path) -> set[str]:
    """Name the branches the bare remote holds."""
    rows = toy.git(project, "ls-remote", "--heads", "origin").splitlines()
    return {row.split("\t")[1].removeprefix("refs/heads/") for row in rows}


def told(project: Path, words: str) -> bool:
    """Whether `interview.md` holds the developer's words, however its lines are cut."""
    return words in " ".join(document(project, "interview.md").read_text(encoding="utf-8").split())


def described(project: Path) -> gh_stand_in.Pull:
    """Give the pull request of the branch, held to what a stop of the chain leaves of it.

    Its description is the one `surface-status pr-body` prints, it is still a draft, and no call
    marked it ready.
    """
    pull = gh_stand_in.pull_of(project, toy.git(project, "branch", "--show-current").strip())
    assert pull is not None
    assert pull.body.strip() == toy.pr_body(project).strip()
    assert pull.draft
    assert not [call.argv for call in gh_stand_in.calls(project) if call.marks_ready]
    return pull


def openings(project: Path) -> list[gh_stand_in.Call]:
    return [call for call in gh_stand_in.calls(project) if call.command == "pr create"]


def final(log: Path) -> str:
    return str(toy.session_result(log).get("result", ""))


def stream(log: Path) -> list[dict[str, Any]]:
    """Read the events of a session's stream, a line cut by a kill left out.

    So is a line still being written, wherever the read cuts it: a stream is read as it grows.
    """
    read: list[dict[str, Any]] = []
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("{"):
            try:
                read.append(json.loads(raw))
            except ValueError:
                continue
    return read


def launches(log: Path) -> list[tuple[str, str]]:
    """List the agents a session launched itself, in order: the id of the call, and the role."""
    return [
        (str(block["id"]), str(block["input"].get("subagent_type")))
        for line in stream(log)
        if line.get("type") == "assistant" and not line.get("parent_tool_use_id")
        for block in line["message"]["content"]
        if block.get("type") == "tool_use" and block.get("name") in {"Agent", "Task"}
    ]


def at_work(log: Path, role: str) -> bool:
    """Whether the last agent a session launched has that role, has begun, and is not back.

    Its return is the notification of the stream, not the result of the call: an agent launched
    in the background gives that result at once, and works on.
    """
    launched = launches(log)
    if not launched or launched[-1][1] != role:
        return False
    call = launched[-1][0]
    begun = back = False
    for line in stream(log):
        if line.get("parent_tool_use_id") == call:
            begun = begun or line.get("type") == "assistant"
        elif line.get("subtype") == "task_notification":
            back = back or line.get("tool_use_id") == call
    return begun and not back


def recorded(project: Path, event: str) -> Callable[[], bool]:
    """Give the moment the journal of the plan holds an event, for a session watched as it runs."""

    def moment() -> bool:
        try:
            return event in events(project)
        except ValueError:
            return False  # no plan folder yet, or a line being written

    return moment


def run_to_end(project: Path, prompt: str, log: Path, *, resume: str | None = None) -> int:
    code = toy.run_session(project, prompt, log, resume=resume)
    if code is None:
        pytest.fail(f"{prompt} still running after {toy.SESSION_TIMEOUT} seconds, killed")
    return code


def say(project: Path, words: str, log: Path, *, resume: str | None = None) -> str:
    """Say one thing to a session, wait for its end, and give its id for the next reply."""
    assert run_to_end(project, words, log, resume=resume) == 0
    return str(toy.session_result(log)["session_id"])


def converse(  # noqa: PLR0913 (one keyword per thing a conversation is given)
    project: Path,
    words: str,
    logs: Path,
    name: str,
    *,
    until: Callable[[], bool],
    resume: str | None = None,
) -> str:
    """Say one thing to a session, then take its recommendation at each question it asks.

    Stops once `until` holds at the end of a session, and gives its id for the next reply.
    """
    for reply in range(MAX_REPLIES):
        resume = say(project, words, logs / f"{name}-{reply + 1:02d}.jsonl", resume=resume)
        if until():
            return resume
        words = RECOMMENDED
    pytest.fail(f"{name}: still not there after {MAX_REPLIES} replies")


def kill_when(
    project: Path, words: str, log: Path, moment: Callable[[], bool], *, resume: str | None = None
) -> None:
    """Start a session and kill it, with what it left at work, as soon as `moment` holds."""
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    met = False
    with log.open("w", encoding="utf-8") as out:
        session = toy.start_claude(project, words, out, resume=resume)
        try:
            while session.poll() is None and time.monotonic() - started < toy.SESSION_TIMEOUT:
                met = moment()
                if met:
                    break
                time.sleep(WATCH)
        finally:
            # Whatever the watch raised, no session is left to run on, billed, behind a scenario.
            if session.poll() is None:
                toy.kill(session, project)
    assert met, f"the session of {log.name} ended, or lasted too long, before the moment to kill it"


# The states a session died in: they keep what that session had not committed yet.
UNCOMMITTED = frozenset(
    {
        toy.State.PLAN_WRITTEN,
        toy.State.BLUEPRINT_DRAWN,
        toy.State.PLANNING_CEILING,
        toy.State.SLICE_UNCOMMITTED,
        toy.State.SUSPECTED_BREAK,
        toy.State.UNFOUNDED_SUSPICION,
        toy.State.REVIEW_UNRECORDED,
    }
)


@pytest.mark.parametrize(
    ("prepared", "expected"),
    [
        (toy.State.PLAN_WRITTEN, "drafting"),
        (toy.State.BLUEPRINT_DRAWN, "drafting"),
        (toy.State.PLANNING_CEILING, "drafting"),
        (toy.State.AWAITING, "awaiting-approval"),
        (toy.State.UNPUSHED, "awaiting-approval"),
        (toy.State.UNPUSHED_CI, "awaiting-approval"),
        (toy.State.TWO_PLANS, "awaiting-approval"),
        (toy.State.SLICE_UNCOMMITTED, "executing"),
        (toy.State.SUSPECTED_BREAK, "executing"),
        (toy.State.UNFOUNDED_SUSPICION, "executing"),
        (toy.State.BLUEPRINT_MODIFIED, "executing"),
        (toy.State.DEVELOPER_BREAK, "reviewing"),
        (toy.State.PROPOSED, "plan-change-proposed"),
        (toy.State.FIXING, "fixing"),
        (toy.State.CEILING, "reviewing"),
        (toy.State.BLOCKED, "blocked"),
        (toy.State.DONE, "reviewing"),
        (toy.State.DEFECT, "reviewing"),
        (toy.State.DEVIATION, "reviewing"),
        (toy.State.REVIEW_UNRECORDED, "reviewing"),
        (toy.State.CONFORMANT_UNPUSHED, "conformant"),
    ],
)
def test_a_prepared_state_is_the_one_named(
    prepared: toy.State, expected: str, tmp_path: Path
) -> None:
    project = toy.build(prepared, tmp_path)
    assert state(project) == expected
    assert dirty(project) is (prepared in UNCOMMITTED)


@pytest.mark.parametrize("prepared", [toy.State.SPECS, toy.State.SPECS_CI])
def test_a_prepared_state_without_a_plan_is_on_the_main_branch(
    prepared: toy.State, tmp_path: Path
) -> None:
    project = toy.build(prepared, tmp_path)
    assert toy.git(project, "branch", "--show-current").strip() == "main"
    assert not list(project.glob("docs/plans/*"))
    assert (project / toy.CI_PATH).is_file() is (prepared is toy.State.SPECS_CI)
    assert not dirty(project)


def test_a_prepared_state_built_slow_holds_a_test_that_lasts(tmp_path: Path) -> None:
    project = toy.build(toy.State.DONE, tmp_path, slow=True)
    assert (project / "tests" / "test_slow.py").is_file()
    assert state(project) == "reviewing"
    assert not dirty(project)


def test_a_prepared_state_never_pushed_has_no_pull_request(tmp_path: Path) -> None:
    project = toy.build(toy.State.UNPUSHED, tmp_path)
    assert on_the_remote(project) == {"main"}
    assert not gh_stand_in.pulls(project)
    # The break of the proposal state is committed, and the push of its stop never came.
    proposed = toy.build(toy.State.PROPOSED, tmp_path / "proposed")
    assert on_the_remote(proposed) == {"main", toy.BRANCH}
    assert not pushed(proposed)


def test_a_session_bypasses_permissions_in_the_container_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(toy.CONTAINER, "1")
    command = toy.claude_command("/surface-execute")
    assert command[command.index("--permission-mode") + 1] == "bypassPermissions"
    assert command[command.index("--setting-sources") + 1] == "project,local"
    assert "--strict-mcp-config" in command
    monkeypatch.delenv(toy.CONTAINER)
    with pytest.raises(toy.OutsideContainerError):
        toy.claude_command("/surface-execute")


def test_a_kill_takes_what_a_session_left_at_work(tmp_path: Path) -> None:
    # A gate runs in a process group of its own, which the kill of the session's group misses.
    idle = ["sleep", "60"]
    session = subprocess.Popen(idle, cwd=tmp_path, text=True, start_new_session=True)
    left = subprocess.Popen(idle, cwd=tmp_path, start_new_session=True)
    assert left.pid in toy.at_work(tmp_path)
    toy.kill(session, tmp_path)
    assert left.wait(timeout=10) == -signal.SIGKILL
    assert not toy.at_work(tmp_path)


def test_the_nominal_path_reaches_conformant(tmp_path: Path) -> None:
    project = toy.build(toy.State.AWAITING, tmp_path)
    assert run_to_end(project, "/surface-execute", tmp_path / "logs" / "execute.jsonl") == 0
    assert state(project) == "conformant"
    seen = events(project)
    assert seen.count("plan-approved") == 1
    assert seen.count("slice-done") == 2
    assert document(project, "conformity.md").is_file()
    # The toy declares the CSV export a critical zone: its code is listed for the developer.
    assert "shelf/export.py" in toy.critical_files(project)
    assert not dirty(project, "shelf", "tests", "docs")
    # The draft /surface-plan would have opened, kept by the stand-in `gh`: the stop refreshed
    # its description, by an edit and no second opening, and nothing marked it ready.
    pull = gh_stand_in.pull_of(project, toy.BRANCH)
    assert pull is not None
    assert pull.body.strip() == toy.pr_body(project).strip()
    assert pull.draft
    calls = gh_stand_in.calls(project)
    assert {call.command for call in calls if call.pull is not None} == {"pr edit"}
    assert not [call.argv for call in calls if call.command == "pr create"]
    assert not [call.argv for call in calls if call.marks_ready]


def test_a_session_killed_in_a_slice_resumes_it(tmp_path: Path) -> None:
    # Built slow: an executor that writes, tests, records and commits in one command still
    # leaves its code uncommitted for as long as its tests run.
    project = toy.build(toy.State.AWAITING, tmp_path, slow=True)
    logs = tmp_path / "logs"
    approved = recorded(project, "plan-approved")
    # Killed as soon as an executor has written code the journal does not cover yet.
    kill_when(
        project,
        "/surface-execute",
        logs / "execute-killed.jsonl",
        lambda: approved() and dirty(project, "shelf", "tests"),
    )
    at_kill = events(project)
    (logs / "journal-at-kill.jsonl").write_text(
        "\n".join(json.dumps(line) for line in journal(project)) + "\n", encoding="utf-8"
    )
    assert run_to_end(project, "/surface-execute", logs / "execute-resumed.jsonl") == 0
    seen = events(project)
    assert seen[: len(at_kill)] == at_kill
    assert seen.count("plan-approved") == 1
    assert seen.count("slice-done") == 2
    assert state(project) == "conformant"


def test_a_modified_blueprint_stops_the_loop(tmp_path: Path) -> None:
    project = toy.build(toy.State.BLUEPRINT_MODIFIED, tmp_path)
    before = events(project)
    log = tmp_path / "logs" / "execute.jsonl"
    assert run_to_end(project, "/surface-execute", log) == 0
    assert events(project) == before
    assert state(project) == "executing"
    assert "blueprint" in str(toy.session_result(log).get("result", "")).lower()


def test_the_ceiling_hands_back_to_the_developer(tmp_path: Path) -> None:
    project = toy.build(toy.State.CEILING, tmp_path)
    assert run_to_end(project, "/surface-execute", tmp_path / "logs" / "execute.jsonl") == 0
    assert state(project) == "blocked"
    lines = journal(project)
    assert lines[-1]["event"] == "blocked"
    reviews = [line for line in lines if line["event"] == "review-done"]
    # The ceiling of one lets one fix run, prepared here: the second review with findings is the
    # pass after the ceiling, recorded, and no second fix follows it.
    assert len(reviews) == 2
    assert reviews[-1]["defects"] + reviews[-1]["deviations"] > 0
    assert events(project).count("fix-done") == 1


def revision_two(project: Path) -> None:
    """Hold the plan to a second revision drafted, awaiting its approval, pushed and described."""
    drafts = [line for line in journal(project) if line["event"] == "plan-drafted"]
    assert [line["rev"] for line in drafts] == [1, 2]
    assert drafts[1]["plan"] != drafts[0]["plan"]
    assert drafts[1]["blueprint"] != drafts[0]["blueprint"]
    assert state(project) == "awaiting-approval"
    assert not dirty(project, "docs")
    assert pushed(project)
    # The draft is the one of revision 1: its description is refreshed, and none is opened.
    described(project)
    assert not openings(project)


def year_first(project: Path) -> bool:
    """Whether the plan and the blueprint carry the amendment: the header in its new order."""
    return all(
        "year,title,author" in re.sub(r"[\s`]", "", document(project, name).read_text("utf-8"))
        for name in ("plan.md", "blueprint.md")
    )


def test_planning_killed_in_the_interview_resumes_at_the_next_question(tmp_path: Path) -> None:
    project = toy.build(toy.State.SPECS, tmp_path)
    logs = tmp_path / "logs"
    session = say(project, f"/surface-plan {NEED}", logs / "need.jsonl")
    if not list(project.glob("docs/plans/*/journal.jsonl")):
        # A question asked before the plan folder exists is about the branch, not the feature.
        session = say(project, RECOMMENDED, logs / "branch.jsonl", resume=session)
    assert state(project) == "interview", "the session asked no question of the interview"
    interview = document(project, "interview.md")
    asked = interview.read_text(encoding="utf-8")
    questions = [line for line in asked.splitlines() if line.startswith("### ") and "<" not in line]
    assert questions, "interview.md holds no question under a heading of its own"
    # Killed as soon as the answer is written: the question was, before it was asked.
    kill_when(
        project,
        RECOMMENDED,
        logs / "answer-killed.jsonl",
        lambda: interview.read_text(encoding="utf-8") != asked,
        resume=session,
    )
    at_kill = events(project)
    explored = document(project, "exploration.md").read_bytes()
    converse(
        project,
        "/surface-plan",
        logs,
        "relaunch",
        until=lambda: state(project) == "awaiting-approval",
    )
    lines = journal(project)
    seen = [line["event"] for line in lines]
    assert seen[: len(at_kill)] == at_kill
    assert [seen.count(event) for event in ("plan-opened", "interview-closed")] == [1, 1]
    # Nothing is explored again, and no question that had its answer is written a second time.
    assert document(project, "exploration.md").read_bytes() == explored
    text = interview.read_text(encoding="utf-8")
    assert [text.count(question) for question in questions] == [1] * len(questions)
    (drafted,) = [line for line in lines if line["event"] == "plan-drafted"]
    assert drafted["gates"] == [toy.GATE_COMMAND]
    assert not dirty(project, "docs")
    assert pushed(project)
    assert len(gh_stand_in.pulls(project)) == 1
    described(project)


def test_an_amendment_killed_once_recorded_is_drafted_at_the_relaunch(tmp_path: Path) -> None:
    project = toy.build(toy.State.AWAITING, tmp_path)
    logs = tmp_path / "logs"
    kill_when(
        project,
        f"/surface-plan {AMENDMENT}",
        logs / "amendment-killed.jsonl",
        recorded(project, "amendment-received"),
    )
    at_kill = events(project)
    # The amendment is written before it is recorded: the relaunch finds it in the files.
    assert told(project, AMENDMENT.rstrip("."))
    converse(
        project,
        "/surface-plan",
        logs,
        "relaunch",
        until=lambda: state(project) == "awaiting-approval",
    )
    seen = events(project)
    assert seen[: len(at_kill)] == at_kill
    assert seen.count("amendment-received") == 1
    revision_two(project)
    assert year_first(project)


def test_a_conversation_after_the_hand_over_amends_and_approves_nothing(tmp_path: Path) -> None:
    project = toy.build(toy.State.AWAITING, tmp_path)
    logs = tmp_path / "logs"
    before = events(project)
    session = say(project, "/surface-plan", logs / "hand-over.jsonl")
    question = "Why are the lines sorted by author before title?"
    session = say(project, question, logs / "question.jsonl", resume=session)
    # A question is answered from the files, and nothing is recorded.
    assert events(project) == before
    assert not dirty(project)
    session = converse(
        project,
        AMENDMENT,
        logs,
        "amendment",
        until=lambda: state(project) == "awaiting-approval" and events(project) != before,
        resume=session,
    )
    amended = events(project)
    assert amended.count("amendment-received") == 1
    assert told(project, AMENDMENT.rstrip("."))
    revision_two(project)
    assert year_first(project)
    agreement = logs / "agreement.jsonl"
    say(project, "Fine, go.", agreement, resume=session)
    # A sentence that agrees approves nothing: only the launch of /surface-execute does.
    assert events(project) == amended
    assert "/surface-execute" in final(agreement)


def header(project: Path, shelf: Path) -> str:
    """Give the first line the export of the project prints for a shelf of one book."""
    book = {"title": "Dune", "author": "Herbert", "year": 1965, "isbn": "9780441013593"}
    shelf.write_text(json.dumps(book) + "\n", encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-m", "shelf", "export", str(shelf)],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.splitlines()[0]


def test_a_break_on_a_commit_of_the_developer_is_raised_then_refused(tmp_path: Path) -> None:
    project = toy.build(toy.State.DEVELOPER_BREAK, tmp_path)
    logs = tmp_path / "logs"
    session = say(project, "/surface-execute", logs / "execute.jsonl")
    assert state(project) == "plan-change-proposed"
    raised = journal(project)[-1]
    assert raised["event"] == "review-done"
    assert raised["breaks"] > 0
    assert document(project, raised["proposal"]).is_file()
    # The loop handed back: the branch is pushed, and the description says whose turn it is.
    assert pushed(project)
    described(project)
    reason = "the import of the bookshop reads three columns"
    refusal = f"I decline it: {reason}, the ISBN stays out."
    session = say(project, refusal, logs / "refusal.jsonl", resume=session)
    if "plan-change-refused" not in events(project):
        # The reason is asked on a line of its own when the refusal is not read as giving it.
        say(project, f"The reason: {reason}.", logs / "reason.jsonl", resume=session)
    lines = journal(project)
    seen = [line["event"] for line in lines]
    assert seen.count("plan-change-refused") == 1
    assert told(project, reason)
    # The same session goes on: the code comes back to the blueprint, and no later review
    # raises the break the developer refused.
    later = lines[seen.index("plan-change-refused") :]
    assert not [line for line in later if line["event"] == "review-done" and line["breaks"]]
    assert state(project) == "conformant"
    assert header(project, tmp_path / "books.jsonl") == "title,author,year"
    assert pushed(project)
    described(project)


def test_an_accepted_plan_change_goes_back_to_planning(tmp_path: Path) -> None:
    project = toy.build(toy.State.PROPOSED, tmp_path)
    logs = tmp_path / "logs"
    before = events(project)
    session = say(project, "/surface-execute", logs / "execute.jsonl")
    # The session that raised the break died between its commit and its push: this one pushes
    # and refreshes the description before it asks, and decides nothing itself.
    assert events(project) == before
    assert pushed(project)
    described(project)
    acceptance = logs / "acceptance.jsonl"
    say(project, "I accept it: the bookshop does want the ISBN.", acceptance, resume=session)
    assert events(project) == [*before, "plan-change-accepted"]
    assert state(project) == "drafting"
    assert told(project, "the bookshop does want the ISBN")
    # The next revision is /surface-plan's to draw: this command names it and stops.
    assert "/surface-plan" in final(acceptance)
    assert not dirty(project, "docs")
    assert pushed(project)
    described(project)


def resumed_past(project: Path, blocked: list[str]) -> None:
    """Hold a plan blocked at the ceiling to what a resumption gives: a fresh count, and work."""
    seen = events(project)
    assert seen[: len(blocked) + 1] == [*blocked, "resumed"]
    assert seen.count("resumed") == 1
    # The count starts again, so a fixer is sent: it leaves a gate run, green or not.
    assert "gates-run" in seen[len(blocked) :]
    assert state(project) in {"conformant", "blocked"}


def test_a_resumption_in_the_session_goes_on_past_the_ceiling(tmp_path: Path) -> None:
    project = toy.build(toy.State.CEILING, tmp_path)
    logs = tmp_path / "logs"
    session = say(project, "/surface-execute", logs / "execute.jsonl")
    assert state(project) == "blocked"
    blocked = events(project)
    say(project, "Resume.", logs / "resumption.jsonl", resume=session)
    resumed_past(project, blocked)


def test_a_relaunch_resumes_a_plan_blocked_at_the_ceiling(tmp_path: Path) -> None:
    project = toy.build(toy.State.BLOCKED, tmp_path)
    blocked = events(project)
    assert run_to_end(project, "/surface-execute", tmp_path / "logs" / "execute.jsonl") == 0
    resumed_past(project, blocked)


def test_an_amendment_takes_a_plan_blocked_at_the_ceiling_back_to_planning(tmp_path: Path) -> None:
    project = toy.build(toy.State.BLOCKED, tmp_path)
    blocked = events(project)
    amendment = "Sort the lines by title alone: the bookshop does not need the order by author."
    converse(
        project,
        f"/surface-plan {amendment}",
        tmp_path / "logs",
        "amendment",
        until=lambda: state(project) == "awaiting-approval",
    )
    lines = journal(project)
    seen = [line["event"] for line in lines]
    assert seen[: len(blocked) + 1] == [*blocked, "amendment-received"]
    assert told(project, "Sort the lines by title alone")
    # The revision is drafted and waits: nothing approves it, and the slices done keep their
    # numbers.
    assert "plan-approved" not in seen[len(blocked) :]
    assert {1, 2} <= set(lines[-1]["slices"])
    revision_two(project)


def test_an_abandon_waits_for_a_yes_then_fails_the_conformity_check(tmp_path: Path) -> None:
    project = toy.build(toy.State.DONE, tmp_path)
    logs = tmp_path / "logs"
    before = events(project)
    session = say(project, "/surface-status abandon", logs / "abandon.jsonl")
    # Nothing is recorded without an explicit yes.
    assert events(project) == before
    assert not dirty(project)
    confirmation = "Yes, abandon it. The bookshop no longer wants the export."
    say(project, confirmation, logs / "confirmation.jsonl", resume=session)
    lines = journal(project)
    assert [line["event"] for line in lines] == [*before, "abandoned"]
    assert "bookshop" in lines[-1]["why"]
    assert state(project) == "abandoned"
    assert not dirty(project, "docs")
    assert pushed(project)
    described(project)
    # The plan was approved: the branch may carry code never declared conformant, and the
    # check of the host's CI fails on it from then on.
    assert toy.check(project) == (1, ["abandoned-after-approval"])


@pytest.mark.parametrize(
    "command",
    ["/surface-plan", "/surface-execute", "/surface-status abandon"],
    ids=["plan", "execute", "abandon"],
)
def test_two_plans_on_a_branch_are_put_to_the_developer(command: str, tmp_path: Path) -> None:
    project = toy.build(toy.State.TWO_PLANS, tmp_path)
    plans = [toy.plan_name(), toy.plan_name(toy.SECOND_SLUG)]
    before = [events(project, plan) for plan in plans]
    log = tmp_path / "logs" / "launch.jsonl"
    assert run_to_end(project, command, log) == 0
    # Neither plan is guessed: nothing is recorded in either, and the question names both.
    assert [events(project, plan) for plan in plans] == before
    assert not dirty(project)
    assert toy.SLUG in final(log)
    assert toy.SECOND_SLUG in final(log)


def test_a_ci_that_runs_on_a_push_makes_planning_wait_for_an_agreement(tmp_path: Path) -> None:
    project = toy.build(toy.State.SPECS_CI, tmp_path)
    logs = tmp_path / "logs"
    session = converse(
        project,
        f"/surface-plan {NEED}",
        logs,
        "need",
        until=recorded(project, "plan-drafted"),
    )
    # The CI of the toy runs on every push and on every pull request: the plan is drafted, and
    # nothing of it has left the machine before the developer agrees.
    assert on_the_remote(project) == {"main"}
    assert not openings(project)
    agreement = "Yes, push it and open the draft."
    say(project, agreement, logs / "agreement.jsonl", resume=session)
    assert state(project) == "awaiting-approval"
    assert pushed(project)
    assert len(gh_stand_in.pulls(project)) == 1
    # The answer is kept, so that a relaunch does not ask again.
    assert told(project, agreement.rstrip("."))
    assert not dirty(project, "docs")
    described(project)


def test_a_push_the_developer_declines_leaves_the_plan_committed_locally(tmp_path: Path) -> None:
    project = toy.build(toy.State.UNPUSHED_CI, tmp_path)
    logs = tmp_path / "logs"
    before = events(project)
    session = say(project, "/surface-plan", logs / "relaunch.jsonl")
    # The first push of the branch is still to come, and the CI runs on it: the session asks.
    assert on_the_remote(project) == {"main"}
    assert not openings(project)
    refusal = logs / "refusal.jsonl"
    say(project, "No, do not push: this plan stays on my machine for now.", refusal, resume=session)
    assert events(project) == before
    assert on_the_remote(project) == {"main"}
    assert not openings(project)
    assert told(project, "do not push")
    assert "local" in final(refusal).lower()


def test_a_draft_committed_and_never_pushed_is_pushed_at_the_relaunch(tmp_path: Path) -> None:
    project = toy.build(toy.State.UNPUSHED, tmp_path)
    before = events(project)
    assert run_to_end(project, "/surface-plan", tmp_path / "logs" / "relaunch.jsonl") == 0
    # The session that drafted the plan died between its commit and its push: the toy has no
    # CI to warn about, so this one pushes and opens the draft without a question.
    assert events(project) == before
    assert pushed(project)
    assert len(gh_stand_in.pulls(project)) == 1
    described(project)


def test_a_session_killed_in_a_fix_resumes_it(tmp_path: Path) -> None:
    project = toy.build(toy.State.FIXING, tmp_path, slow=True)
    logs = tmp_path / "logs"
    # Killed as soon as the fixer has changed code it has not committed yet: built slow, the
    # project keeps that code uncommitted for as long as the gates of the fix run.
    kill_when(
        project,
        "/surface-execute",
        logs / "execute-killed.jsonl",
        lambda: dirty(project, "shelf", "tests"),
    )
    at_kill = events(project)
    assert "fix-done" not in at_kill
    assert run_to_end(project, "/surface-execute", logs / "execute-resumed.jsonl") == 0
    seen = events(project)
    assert seen[: len(at_kill)] == at_kill
    assert "fix-done" in seen
    assert state(project) == "conformant"
    assert not dirty(project, "shelf", "tests", "docs")


def test_a_session_killed_in_a_gate_run_runs_the_gates_again(tmp_path: Path) -> None:
    project = toy.build(toy.State.DONE, tmp_path, slow=True)
    logs = tmp_path / "logs"
    before = events(project)
    # Killed while the gate of the plan runs: the state script started it, in a group of its own.
    kill_when(
        project,
        "/surface-execute",
        logs / "execute-killed.jsonl",
        lambda: any(
            command.endswith(toy.GATE_COMMAND) for command in toy.at_work(project).values()
        ),
    )
    # The run died with its session: it left neither a result nor a report.
    assert events(project) == before
    assert not list(document(project, "gates").glob("*"))
    assert run_to_end(project, "/surface-execute", logs / "execute-resumed.jsonl") == 0
    lines = journal(project)
    assert [line["event"] for line in lines][: len(before)] == before
    runs = [line for line in lines if line["event"] == "gates-run"]
    assert (runs[0]["run"], runs[0]["result"]) == (1, "pass")
    assert state(project) == "conformant"


def test_a_session_killed_in_a_review_launches_it_again(tmp_path: Path) -> None:
    project = toy.build(toy.State.DONE, tmp_path)
    logs = tmp_path / "logs"
    killed = logs / "execute-killed.jsonl"
    kill_when(project, "/surface-execute", killed, lambda: at_work(killed, "surface-reviewer"))
    at_kill = events(project)
    assert "review-done" not in at_kill
    assert run_to_end(project, "/surface-execute", logs / "execute-resumed.jsonl") == 0
    seen = events(project)
    assert seen[: len(at_kill)] == at_kill
    # The gates were green before the kill and nothing changed since: they do not run again
    # before the review the relaunch owes.
    assert seen[: seen.index("review-done")].count("gates-run") == 1
    assert state(project) == "conformant"


def test_a_review_written_and_not_recorded_is_recorded_at_the_relaunch(tmp_path: Path) -> None:
    project = toy.build(toy.State.REVIEW_UNRECORDED, tmp_path)
    before = events(project)
    report = document(project, "reviews/pass-01.md").read_bytes()
    log = tmp_path / "logs" / "execute.jsonl"
    assert run_to_end(project, "/surface-execute", log) == 0
    lines = journal(project)
    # The report the interrupted reviewer left is its return: it is recorded as it stands, and
    # no second reviewer is launched.
    assert [line["event"] for line in lines][: len(before)] == before
    assert lines[len(before)]["event"] == "review-done"
    assert lines[len(before)]["report"] == "reviews/pass-01.md"
    assert document(project, "reviews/pass-01.md").read_bytes() == report
    assert "surface-reviewer" not in [role for _, role in launches(log)]
    assert state(project) == "conformant"
    assert not dirty(project, "docs")
    assert pushed(project)
    described(project)


@pytest.mark.xfail(
    strict=True,
    reason="a plan that is over is found by no relaunch, so its push is left to nobody (#114)",
)
def test_a_conformant_plan_committed_and_never_pushed_is_pushed_at_the_relaunch(
    tmp_path: Path,
) -> None:
    project = toy.build(toy.State.CONFORMANT_UNPUSHED, tmp_path)
    before = events(project)
    assert run_to_end(project, "/surface-execute", tmp_path / "logs" / "execute.jsonl") == 0
    # The session that recorded the conformity died between its commit and its push. The plan
    # is over and nothing is left to record: the stop is still owed its push and its refresh.
    assert events(project) == before
    assert pushed(project)
    described(project)


def first_commit(project: Path, start: str) -> list[str]:
    """List the files of the first commit made after `start`."""
    first = toy.git(project, "rev-list", "--reverse", f"{start}..HEAD").split()[0]
    return sorted(toy.git(project, "show", "--name-only", "--format=", first).split())


def test_a_slice_recorded_and_not_committed_is_committed_at_the_relaunch(tmp_path: Path) -> None:
    project = toy.build(toy.State.SLICE_UNCOMMITTED, tmp_path)
    before = events(project)
    start = toy.git(project, "rev-parse", "HEAD").strip()
    assert run_to_end(project, "/surface-execute", tmp_path / "logs" / "execute.jsonl") == 0
    seen = events(project)
    assert seen[: len(before)] == before
    assert seen.count("slice-done") == 2
    # The first commit of the relaunch is the one the executor did not make: the work of
    # slice 1 with the journal line that records it, and nothing else.
    assert first_commit(project, start) == [
        f"docs/plans/{plan_of(project)}/journal.jsonl",
        "shelf/export.py",
        "tests/test_export.py",
    ]
    assert state(project) == "conformant"


@pytest.mark.parametrize(
    ("prepared", "agent"),
    [
        (toy.State.PLAN_WRITTEN, "surface-extractor"),
        (toy.State.BLUEPRINT_DRAWN, "surface-checker"),
    ],
    ids=["extraction", "cross_check"],
)
def test_planning_killed_while_an_agent_works_drafts_the_plan_at_the_relaunch(
    prepared: toy.State, agent: str, tmp_path: Path
) -> None:
    project = toy.build(prepared, tmp_path)
    logs = tmp_path / "logs"
    before = events(project)
    killed = logs / "plan-killed.jsonl"
    kill_when(project, "/surface-plan", killed, lambda: at_work(killed, agent))
    at_kill = events(project)
    assert "plan-drafted" not in at_kill
    converse(
        project,
        "/surface-plan",
        logs,
        "relaunch",
        until=lambda: state(project) == "awaiting-approval",
    )
    seen = events(project)
    assert seen[: len(at_kill)] == at_kill
    assert seen[: len(before)] == before
    assert seen.count("plan-drafted") == 1
    assert not dirty(project, "docs")
    assert pushed(project)
    assert len(gh_stand_in.pulls(project)) == 1
    described(project)


def test_the_ceiling_in_planning_hands_back_then_takes_an_instruction(tmp_path: Path) -> None:
    project = toy.build(toy.State.PLANNING_CEILING, tmp_path)
    logs = tmp_path / "logs"
    before = events(project)
    first = logs / "plan.jsonl"
    session = say(project, "/surface-plan", first)
    # Two cross-checks counted the omission and the ceiling is one: nothing more is launched,
    # and the block is committed with the plan folder.
    assert events(project) == [*before, "blocked"]
    assert not launches(first)
    assert not dirty(project, "docs")
    instruction = "Draw the blueprint again: it must show that the command rewrites the shelf file."
    converse(
        project,
        instruction,
        logs,
        "instruction",
        until=lambda: (
            "resumed" in events(project) and state(project) in {"awaiting-approval", "blocked"}
        ),
        resume=session,
    )
    seen = events(project)
    assert seen[: len(before) + 2] == [*before, "blocked", "resumed"]
    assert told(project, instruction.rstrip("."))
    # The count starts again: the blueprint is drawn and cross-checked once more at least.
    assert "check-done" in seen[len(before) + 2 :]


def test_a_break_suspected_in_a_slice_is_confirmed_at_the_relaunch_then_refused(
    tmp_path: Path,
) -> None:
    project = toy.build(toy.State.SUSPECTED_BREAK, tmp_path)
    logs = tmp_path / "logs"
    before = events(project)
    first = logs / "execute.jsonl"
    session = say(project, "/surface-execute", first)
    lines = journal(project)
    # The executor's reason waited in the journal: a reviewer judges it before anything carries
    # the slice on, and confirms it.
    assert [role for _, role in launches(first)] == ["surface-reviewer"]
    assert [line["event"] for line in lines] == [*before, "plan-change-proposed"]
    assert lines[-1]["slice"] == 2
    assert document(project, lines[-1]["proposal"]).is_file()
    # The proposal, the unfinished work of the slice and the journal are committed and pushed.
    assert not dirty(project)
    assert pushed(project)
    described(project)
    reason = "nothing reads the JSON export any more"
    refusal = f"I decline it: {reason}, replace it. The blueprint stays as it is."
    session = say(project, refusal, logs / "refusal.jsonl", resume=session)
    if "plan-change-refused" not in events(project):
        say(project, f"The reason: {reason}.", logs / "reason.jsonl", resume=session)
    lines = journal(project)
    seen = [line["event"] for line in lines]
    assert seen.count("plan-change-refused") == 1
    assert told(project, reason)
    # Back to the slice, done once, and the break the developer refused is not raised again.
    later = lines[seen.index("plan-change-refused") :]
    assert [line["event"] for line in later].count("slice-done") == 1
    assert "plan-change-proposed" not in [line["event"] for line in later]
    assert not [line for line in later if line["event"] == "review-done" and line["breaks"]]
    assert state(project) == "conformant"
    assert header(project, tmp_path / "books.jsonl") == "title,author,year"


def test_a_break_suspected_in_a_slice_is_dismissed_at_the_relaunch(tmp_path: Path) -> None:
    project = toy.build(toy.State.UNFOUNDED_SUSPICION, tmp_path)
    before = events(project)
    start = toy.git(project, "rev-parse", "HEAD").strip()
    log = tmp_path / "logs" / "execute.jsonl"
    assert run_to_end(project, "/surface-execute", log) == 0
    lines = journal(project)
    seen = [line["event"] for line in lines]
    assert seen[: len(before)] == before
    dismissed = lines[len(before)]
    assert (dismissed["event"], dismissed["slice"]) == ("suspicion-dismissed", 2)
    # The note and the journal are committed, not the work: the next executor takes the slice
    # up from it, with the note.
    plan = f"docs/plans/{plan_of(project)}"
    assert first_commit(project, start) == sorted(
        [f"{plan}/journal.jsonl", f"{plan}/{dismissed['report']}"]
    )
    assert [role for _, role in launches(log)][:2] == ["surface-reviewer", "surface-executor"]
    assert seen.count("slice-done") == 2
    assert "plan-change-proposed" not in seen
    assert state(project) == "conformant"
