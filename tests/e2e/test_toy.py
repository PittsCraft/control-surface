"""End to end: `/surface-execute` on the toy project, headless, from prepared states (ADR 0025).

Billed and slow: run on demand only, with `scripts/gate.sh e2e`, never in CI. Each scenario keeps
the stream of its sessions under `logs/` next to the toy project, in pytest's temporary folder
(`--basetemp` chooses it). The interactive scenarios, `/surface-plan` and the refusal of a plan
change, are run by hand: see `tests/e2e/README.md`.
"""

import json
import time
from pathlib import Path
from typing import Any

import pytest
import toy

POLL = 2  # seconds between two looks at a running session


def journal(project: Path) -> list[dict[str, Any]]:
    path = project / "docs" / "plans" / toy.plan_name() / "journal.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def events(project: Path) -> list[str]:
    return [line["event"] for line in journal(project)]


def state(project: Path) -> str:
    shown = toy.show(project, f"docs/plans/{toy.plan_name()}")
    return str(shown["state"])


def dirty(project: Path, *paths: str) -> bool:
    return bool(toy.git(project, "status", "--porcelain", "--", *paths).strip())


def run_to_end(project: Path, prompt: str, log: Path) -> int:
    code = toy.run_session(project, prompt, log)
    if code is None:
        pytest.fail(f"{prompt} still running after {toy.SESSION_TIMEOUT} seconds, killed")
    return code


@pytest.mark.parametrize(
    ("prepared", "expected"),
    [
        (toy.State.AWAITING, "awaiting-approval"),
        (toy.State.OVERVIEW_MODIFIED, "executing"),
        (toy.State.DEVELOPER_BREAK, "reviewing"),
        (toy.State.CEILING, "reviewing"),
    ],
)
def test_a_prepared_state_is_the_one_named(
    prepared: toy.State, expected: str, tmp_path: Path
) -> None:
    project = toy.build(prepared, tmp_path)
    assert state(project) == expected
    assert not dirty(project)


def test_the_nominal_path_reaches_conform(tmp_path: Path) -> None:
    project = toy.build(toy.State.AWAITING, tmp_path)
    assert run_to_end(project, "/surface-execute", tmp_path / "logs" / "execute.jsonl") == 0
    assert state(project) == "conform"
    seen = events(project)
    assert seen.count("plan-approved") == 1
    assert seen.count("slice-done") == 2
    assert (project / "docs" / "plans" / toy.plan_name() / "conformity.md").is_file()
    assert not dirty(project, "shelf", "tests", "docs")


def test_a_session_killed_in_a_slice_resumes_it(tmp_path: Path) -> None:
    project = toy.build(toy.State.AWAITING, tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir()
    started = time.monotonic()
    with (logs / "execute-killed.jsonl").open("w", encoding="utf-8") as out:
        session = toy.start_claude(project, "/surface-execute", out)
        # Killed as soon as an executor has written code the journal does not cover yet.
        while session.poll() is None and time.monotonic() - started < toy.SESSION_TIMEOUT:
            if "plan-approved" in events(project) and dirty(project, "shelf", "tests"):
                break
            time.sleep(POLL)
        assert session.poll() is None, "the session ended before any slice was under way"
        toy.kill(session)
    at_kill = events(project)
    (logs / "journal-at-kill.jsonl").write_text(
        "\n".join(json.dumps(line) for line in journal(project)) + "\n", encoding="utf-8"
    )
    assert run_to_end(project, "/surface-execute", logs / "execute-resumed.jsonl") == 0
    seen = events(project)
    assert seen[: len(at_kill)] == at_kill
    assert seen.count("plan-approved") == 1
    assert seen.count("slice-done") == 2
    assert state(project) == "conform"


def test_a_modified_overview_stops_the_loop(tmp_path: Path) -> None:
    project = toy.build(toy.State.OVERVIEW_MODIFIED, tmp_path)
    before = events(project)
    log = tmp_path / "logs" / "execute.jsonl"
    assert run_to_end(project, "/surface-execute", log) == 0
    assert events(project) == before
    assert state(project) == "executing"
    assert "overview" in str(toy.session_result(log).get("result", "")).lower()


def test_the_ceiling_hands_back_to_the_developer(tmp_path: Path) -> None:
    project = toy.build(toy.State.CEILING, tmp_path)
    assert run_to_end(project, "/surface-execute", tmp_path / "logs" / "execute.jsonl") == 0
    assert state(project) == "blocked"
    lines = journal(project)
    assert lines[-1]["event"] == "blocked"
    reviews = [line for line in lines if line["event"] == "review-done"]
    assert len(reviews) == 1
    assert reviews[0]["defects"] + reviews[0]["deviations"] > 0
