"""Properties of the command line over random walks of a plan: replay, frozen overview, check.

A walk mixes guided steps (the event that moves the plan on), random steps (most of them refused)
and edits of `overview.md`. Every step goes through `main`, as a skill would.
"""

import json
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cli_support import Project
from hypothesis import event as note
from hypothesis import given
from hypothesis import strategies as st

from surface_status.events import Abandoned, Conform, Event, PlanApproved
from surface_status.journal import read_events
from surface_status.plan_folder import PlanFolder

_REVIEW = ("--defects", "0", "--deviations", "0", "--breaks", "0")
_DEFECT = ("--defects", "1", "--deviations", "0", "--breaks", "0")
_BREAK = ("--defects", "0", "--deviations", "0", "--breaks", "1")
Call = tuple[str, tuple[str, ...]]
CALLS: tuple[Call, ...] = (
    ("plan-opened", ()),
    ("interview-closed", ()),
    ("check-done", ("--report", "checks/rev-01-01.md", "--omissions", "0")),
    ("check-done", ("--report", "checks/rev-01-01.md", "--omissions", "1")),
    ("plan-drafted", ()),
    ("amendment-received", ()),
    ("plan-approved", ()),
    ("slice-done", ("--slice", "1", "--gates", "lint")),
    ("slice-done", ("--slice", "2", "--gates", "lint")),
    ("plan-amended", ("--slice", "1", "--why", "renamed")),
    ("suspicion-dismissed", ("--slice", "1", "--report", "reviews/suspicion-01.md")),
    ("plan-change-proposed", ("--proposal", "plan-changes/01.md", "--slice", "1")),
    ("review-done", ("--report", "reviews/pass-01.md", *_REVIEW)),
    ("review-done", ("--report", "reviews/pass-01.md", *_DEFECT)),
    (
        "review-done",
        ("--report", "reviews/pass-01.md", *_BREAK, "--proposal", "plan-changes/01.md"),
    ),
    ("fix-done", ()),
    ("plan-change-accepted", ()),
    ("plan-change-refused", ("--why", "not needed")),
    ("blocked", ("--why", "does not converge")),
    ("resumed", ()),
    ("conform", ("--conformity", "conformity.md")),
    ("abandoned", ("--why", "changed course")),
)
# What moves a plan on, by state: the guided steps.
ONWARD: dict[str, Call] = {
    "interview": CALLS[1],
    "awaiting-approval": CALLS[6],
    "reviewing": CALLS[12],
    "fixing": CALLS[15],
    "plan-change-proposed": CALLS[17],
    "blocked": CALLS[19],
}
FILES = (
    "checks/rev-01-01.md",
    "reviews/pass-01.md",
    "reviews/suspicion-01.md",
    "plan-changes/01.md",
    "conformity.md",
)
OVERVIEWS = ("# Overview\n", "# Overview\nedited\n")


@contextmanager
def _project() -> Generator[tuple[Project, Path]]:
    with tempfile.TemporaryDirectory() as directory:
        project = Project(Path(directory))
        folder = project.plan()
        for name in FILES:
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text("report\n", encoding="utf-8")
        yield project, folder


def _show(project: Project) -> dict[str, Any]:
    return project.run("show", "2026-09-29-feature").json()


def _state(project: Project) -> str | None:
    state: str | None = _show(project)["state"]
    return state


@st.composite
def _steps(draw: st.DrawFn) -> list[tuple[str, Call | int]]:
    steps: list[tuple[str, Call | int]] = []
    for _ in range(draw(st.integers(0, 30))):
        kind = draw(st.sampled_from(["guided"] * 8 + ["random"] * 2 + ["edit"]))
        if kind == "random":
            steps.append((kind, draw(st.sampled_from(CALLS))))
        elif kind == "edit":
            steps.append((kind, draw(st.integers(0, 1))))
        else:
            steps.append((kind, ("", ())))
    return steps


def _choose(project: Project, step: tuple[str, Call | int]) -> Call | None:  # noqa: PLR0911 (one arm per state)
    """Pick the step: the one given when random, else the one that moves the plan on."""
    kind, payload = step
    if kind == "random":
        return payload  # type: ignore[return-value]
    shown = _show(project)
    state, last = shown["state"], shown["last_event"]
    if state is None:
        return ("plan-opened", ())
    if state == "drafting" and last == "check-done":
        return CALLS[4]  # plan-drafted, once a cross-check came back clean
    if state == "drafting":
        return CALLS[2]
    if state == "reviewing" and last == "review-done":
        return CALLS[20]  # conform, once a review came back clean
    if state == "executing":
        following = shown["slices"]["remaining"][0]
        return ("slice-done", ("--slice", str(following), "--gates", "lint"))
    return ONWARD.get(state)


def _apply(project: Project, folder: Path, step: tuple[str, Call | int]) -> None:
    """Run one step, and check what every step must keep true."""
    kind, payload = step
    if kind == "edit":
        (folder / "overview.md").write_text(OVERVIEWS[int(payload)], encoding="utf-8")  # type: ignore[arg-type]
        return
    call = _choose(project, step)
    if call is None:
        return
    name, args = call
    before = project.journal()
    result = project.record("2026-09-29-feature", name, *args)
    after = project.journal()
    answer = result.json()
    assert answer["v"] == 1
    assert result.code in {0, 1}, result
    if result.code == 0:
        assert after.startswith(before)
        assert after[len(before) :].count(b"\n") == 1
        assert after.endswith(b"\n")
        assert answer["state"] == _state(project)
    else:
        assert after == before
    assert project.run("check").code == 0  # whatever happened, the journal still replays


def _walk(project: Project, folder: Path, steps: list[tuple[str, Call | int]]) -> None:
    for step in steps:
        _apply(project, folder, step)


@given(steps=_steps())
def test_a_refused_record_leaves_the_journal_unchanged_and_an_accepted_one_appends_one_line(
    steps: list[tuple[str, Call | int]],
) -> None:
    with _project() as (project, folder):
        _walk(project, folder, steps)


def _oracle(events: list[Event], overview: str | None) -> bool:
    """Whether `check --require conform` must pass, worked out from the raw events."""
    approvals = [event for event in events if isinstance(event, PlanApproved)]
    match events[-1] if events else None:
        case Conform():
            return bool(approvals) and overview == approvals[-1].overview
        case Abandoned():
            return not approvals
        case _:
            return False


@given(steps=_steps())
def test_the_check_passes_exactly_when_the_plan_is_conform_and_untouched_or_dropped_early(
    steps: list[tuple[str, Call | int]],
) -> None:
    with _project() as (project, folder):
        _walk(project, folder, steps)
        journal = folder / "journal.jsonl"
        expected = not journal.exists() or _oracle(
            read_events(journal), PlanFolder(folder).overview_hash()
        )
        note(f"expected {expected}, final {_state(project) if journal.exists() else 'no journal'}")
        result = project.run("check", "--require", "conform")
        assert result.code == (0 if expected else 1), (steps, result.out)
        assert result.json()["ok"] is expected


@given(steps=_steps())
def test_the_list_and_show_agree_with_the_journal_on_every_walk(
    steps: list[tuple[str, Call | int]],
) -> None:
    with _project() as (project, folder):
        _walk(project, folder, steps)
        listed = project.run()
        assert listed.code == 0
        rows = listed.json()["plans"]
        journal = folder / "journal.jsonl"
        if not journal.exists():
            assert rows == []
            return
        shown = project.run("show", folder.name).json()
        assert rows == [
            {"name": folder.name, "state": shown["state"], "hand": shown["hand"]},
        ]
        events = read_events(journal)
        assert shown["last_event"] == (events[-1].name if events else None)
        assert json.loads(json.dumps(shown)) == shown
