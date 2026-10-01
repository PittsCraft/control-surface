"""Recording an event: the journal only ever grows by one accepted line (ADR 0012)."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import event as note
from hypothesis import given
from hypothesis import strategies as st
from journal_support import (
    GATES,
    NOW,
    make_event,
    new_folder,
    onward,
    plan_text,
    settings_with,
    write,
)

from surface_status.events import (
    EVENT_NAMES,
    Abandoned,
    CheckDone,
    Conform,
    GateResult,
    GatesRun,
    InterviewClosed,
    PlanAmended,
    PlanApproved,
    PlanDrafted,
    PlanOpened,
    ReviewDone,
    SliceDone,
)
from surface_status.guards import Accepted, InvalidJournalError, Refusal, RefusalCode
from surface_status.journal import JournalError, decode_line, read_events
from surface_status.machine import State
from surface_status.plan_folder import PlanFolder, PlanFolderError, parse_critical_files
from surface_status.record import load_state, record, timestamp
from surface_status.settings import Settings

DEFAULTS = Settings()


def _accept(folder: PlanFolder, event: object, settings: Settings = DEFAULTS) -> None:
    result = record(folder, event, settings, NOW)  # type: ignore[arg-type]
    assert isinstance(result, Accepted), result


def _refusal(folder: PlanFolder, event: object, settings: Settings = DEFAULTS) -> Refusal:
    result = record(folder, event, settings, NOW)  # type: ignore[arg-type]
    assert isinstance(result, Refusal), result
    return result


def _bytes(folder: PlanFolder) -> bytes:
    return folder.journal.read_bytes() if folder.journal.exists() else b""


def _to_drafting(folder: PlanFolder) -> None:
    _accept(folder, PlanOpened(slug=folder.name))
    _accept(folder, InterviewClosed())


def _to_awaiting(folder: PlanFolder) -> None:
    _to_drafting(folder)
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    report = write(folder, folder.next_check(1))
    _accept(folder, CheckDone(rev=1, report=report, omissions=0, overview=overview, plan=plan))
    _accept(folder, PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1, 2), gates=GATES))


def _to_executing(folder: PlanFolder) -> None:
    _to_awaiting(folder)
    overview = folder.overview_hash()
    assert overview is not None
    _accept(folder, PlanApproved(rev=1, overview=overview))


def test_a_plan_walks_from_opening_to_conform_through_record(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    settings = settings_with(3)
    _to_executing(folder)
    _accept(folder, SliceDone(slice_=1, gates="lint"), settings)
    _accept(folder, SliceDone(slice_=2, gates="lint"), settings)
    run = folder.next_gate_run()
    write(folder, f"gates/run-{run:02d}.txt")
    _accept(folder, GatesRun(run=run, result=GateResult.PASS), settings)
    report = write(folder, folder.next_review())
    _accept(
        folder,
        ReviewDone(pass_=1, report=report, defects=0, deviations=0, breaks=0),
        settings,
    )
    overview = folder.overview_hash()
    assert overview is not None
    _accept(folder, Conform(conformity=write(folder, "conformity.md"), overview=overview), settings)
    state = load_state(folder)
    assert state is not None
    assert state.state is State.CONFORM
    assert len(read_events(folder.journal)) == 10


def test_each_line_carries_the_utc_time_of_the_record(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    paris = timezone(timedelta(hours=2))
    result = record(
        folder, PlanOpened(slug=folder.name), DEFAULTS, datetime(2026, 9, 29, 11, 0, tzinfo=paris)
    )
    assert isinstance(result, Accepted)
    assert decode_line(folder.journal.read_text(encoding="utf-8").rstrip("\n")).at == (
        "2026-09-29T09:00:00Z"
    )
    assert timestamp(NOW) == "2026-09-29T09:00:00Z"
    with pytest.raises(ValueError, match="time zone"):
        timestamp(datetime(2026, 9, 29, 9, 0, tzinfo=None))  # noqa: DTZ001


@given(st.integers(1, 40), st.integers(1, 3), st.booleans(), st.data())
def test_a_refused_record_leaves_the_journal_unchanged_and_an_accepted_one_only_appends(
    steps: int,
    ceiling: int,
    gates: bool,  # noqa: FBT001 (hypothesis passes arguments by position)
    data: st.DataObject,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        named = GATES if gates else ()
        folder = new_folder(Path(directory), gates=named)
        settings = settings_with(ceiling)
        for step in range(steps):
            state = load_state(folder)
            edit = data.draw(st.integers(0, 14))
            if edit == 0:
                folder.overview.write_text(f"overview {step}\n", encoding="utf-8")
            elif edit == 1:
                marks = data.draw(st.lists(st.integers(1, 3), unique=True, min_size=1, max_size=3))
                folder.plan.write_text(
                    plan_text(tuple(marks), named, f"step {step}\n"), encoding="utf-8"
                )
            name = onward(state)
            if name is None or data.draw(st.integers(0, 2)) == 0:
                name = data.draw(st.sampled_from(EVENT_NAMES))
            before = _bytes(folder)
            event = make_event(name, folder, state, data)
            result = record(folder, event, settings, NOW)
            after = _bytes(folder)
            if isinstance(result, Refusal):
                note(f"refused {result.code}")
                assert after == before
            else:
                note(f"accepted {name}")
                assert after.startswith(before)
                assert after[len(before) :].count(b"\n") == 1
                assert read_events(folder.journal)[-1] == event
                assert load_state(folder) == result.state


def test_a_journal_that_does_not_replay_stops_the_record_and_is_left_alone(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    lines = folder.journal.read_bytes().splitlines(keepends=True)
    folder.journal.write_bytes(lines[0] + lines[0])  # plan-opened twice
    before = _bytes(folder)
    with pytest.raises(InvalidJournalError):
        record(folder, InterviewClosed(), DEFAULTS, NOW)
    folder.journal.write_bytes(before + b"{")
    with pytest.raises(JournalError, match="newline"):
        record(folder, Abandoned(why="stop"), DEFAULTS, NOW)
    assert _bytes(folder) == before + b"{"


def test_a_folder_that_does_not_exist_is_an_error_not_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(PlanFolderError, match="not a plan folder"):
        record(PlanFolder(tmp_path / "gone"), PlanOpened(slug="x"), DEFAULTS, NOW)


# Record-time guards


def test_a_cited_file_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    before = _bytes(folder)
    event = CheckDone(
        rev=1, report="checks/rev-01-01.md", omissions=0, overview=overview, plan=plan
    )
    refusal = _refusal(folder, event)
    assert refusal.code is RefusalCode.FILE_MISSING
    assert "checks/rev-01-01.md" in refusal.reason
    assert _bytes(folder) == before
    write(folder, "checks/rev-01-01.md")
    _accept(folder, event)


@pytest.mark.parametrize("name", ["../outside.md", "/etc/hosts", "checks", "gates/run-01.txt"])
def test_a_cited_name_that_is_not_a_file_of_the_folder_is_refused(
    tmp_path: Path, name: str
) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    (folder.root / "checks").mkdir()
    (tmp_path / "outside.md").write_text("x", encoding="utf-8")
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    event = CheckDone(rev=1, report=name, omissions=0, overview=overview, plan=plan)
    assert _refusal(folder, event).code is RefusalCode.FILE_MISSING


def test_a_gate_run_is_cited_by_its_number(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    settings = settings_with(3)
    _to_executing(folder)
    _accept(folder, SliceDone(slice_=1, gates="x"), settings)
    _accept(folder, SliceDone(slice_=2, gates="x"), settings)
    event = GatesRun(run=1, result=GateResult.PASS)
    assert _refusal(folder, event, settings).code is RefusalCode.FILE_MISSING
    write(folder, "gates/run-01.txt")
    _accept(folder, event, settings)


def test_plan_drafted_is_refused_when_the_last_check_found_omissions(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    report = write(folder, folder.next_check(1))
    _accept(folder, CheckDone(rev=1, report=report, omissions=2, overview=overview, plan=plan))
    before = _bytes(folder)
    refusal = _refusal(folder, PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1, 2)))
    assert refusal.code is RefusalCode.CROSS_CHECK
    assert "2 omissions" in refusal.reason
    assert _bytes(folder) == before


def test_plan_drafted_is_refused_when_the_check_covered_other_hashes(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    report = write(folder, folder.next_check(1))
    _accept(folder, CheckDone(rev=1, report=report, omissions=0, overview=overview, plan=plan))
    folder.plan.write_text(
        "<!-- slice:1 -->\n<!-- slice:2 -->\nedited after the check\n", encoding="utf-8"
    )
    new_plan = folder.plan_hash()
    assert new_plan is not None
    before = _bytes(folder)
    refusal = _refusal(folder, PlanDrafted(rev=1, overview=overview, plan=new_plan, slices=(1, 2)))
    assert refusal.code is RefusalCode.CROSS_CHECK
    assert "did not cover" in refusal.reason
    assert _bytes(folder) == before


def test_a_hash_read_before_the_file_changed_is_refused(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    report = write(folder, folder.next_check(1))
    folder.overview.write_text("# Overview, edited\n", encoding="utf-8")
    stale = CheckDone(rev=1, report=report, omissions=0, overview=overview, plan=plan)
    assert _refusal(folder, stale).code is RefusalCode.HASH_STALE
    folder.overview.write_text("# Overview\n", encoding="utf-8")
    folder.plan.write_text("<!-- slice:1 -->\nedited\n", encoding="utf-8")
    assert _refusal(folder, stale).code is RefusalCode.HASH_STALE


def test_the_slices_of_a_draft_are_the_ones_the_plan_declares(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    report = write(folder, folder.next_check(1))
    _accept(folder, CheckDone(rev=1, report=report, omissions=0, overview=overview, plan=plan))
    refusal = _refusal(folder, PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1, 2, 3)))
    assert refusal.code is RefusalCode.SLICES_STALE


def test_a_plan_with_a_duplicated_marker_cannot_be_drafted(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    folder.plan.write_text("<!-- slice:1 -->\n<!-- slice:1 -->\n", encoding="utf-8")
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    report = write(folder, folder.next_check(1))
    _accept(folder, CheckDone(rev=1, report=report, omissions=0, overview=overview, plan=plan))
    refusal = _refusal(folder, PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1,)))
    assert refusal.code is RefusalCode.SLICES_STALE
    assert "declared twice" in refusal.reason


def test_the_overview_edited_after_approval_blocks_the_next_record(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_executing(folder)
    folder.overview.write_text("# Overview, edited after approval\n", encoding="utf-8")
    refusal = _refusal(folder, SliceDone(slice_=1, gates="lint"))
    assert refusal.code is RefusalCode.OVERVIEW_CHANGED
    folder.overview.unlink()
    assert _refusal(folder, SliceDone(slice_=1, gates="lint")).code is RefusalCode.OVERVIEW_CHANGED


def test_a_plan_amended_carries_the_current_plan_hash_and_slices(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_executing(folder)
    folder.plan.write_text(plan_text((1, 2, 3)), encoding="utf-8")
    plan = folder.plan_hash()
    assert plan is not None
    stale = PlanAmended(slice_=1, why="added a slice", plan=plan, slices=(1, 2))
    assert _refusal(folder, stale).code is RefusalCode.SLICES_STALE
    _accept(folder, PlanAmended(slice_=1, why="added a slice", plan=plan, slices=(1, 2, 3)))


def test_the_ceiling_comes_from_the_settings(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    for _ in range(3):  # two reworks, then the pass past the ceiling, recorded
        report = write(folder, folder.next_check(1))
        event = CheckDone(rev=1, report=report, omissions=1, overview=overview, plan=plan)
        _accept(folder, event, settings_with(2))
    report = write(folder, folder.next_check(1))
    fourth = CheckDone(rev=1, report=report, omissions=1, overview=overview, plan=plan)
    assert _refusal(folder, fourth, settings_with(2)).code is RefusalCode.CEILING
    _accept(folder, fourth, settings_with(3))


# The gates block of the plan


def _checked(folder: PlanFolder) -> tuple[str, str]:
    """Record a clean cross-check of the files as they are, and return their hashes."""
    overview, plan = folder.overview_hash(), folder.plan_hash()
    assert overview is not None
    assert plan is not None
    report = write(folder, folder.next_check(1))
    _accept(folder, CheckDone(rev=1, report=report, omissions=0, overview=overview, plan=plan))
    return overview, plan


def test_a_plan_without_its_gates_block_cannot_be_drafted(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    folder.plan.write_text(plan_text(gates=None), encoding="utf-8")
    overview, plan = _checked(folder)
    before = _bytes(folder)
    refusal = _refusal(folder, PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1, 2)))
    assert refusal.code is RefusalCode.GATE_LIST
    assert "no gates block" in refusal.reason
    assert _bytes(folder) == before


def test_the_gates_of_a_draft_are_the_ones_the_plan_names(tmp_path: Path) -> None:
    folder = new_folder(tmp_path, gates=("make test", "make lint"))
    _to_drafting(folder)
    overview, plan = _checked(folder)
    stale = PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1, 2), gates=("make test",))
    assert _refusal(folder, stale).code is RefusalCode.GATE_LIST
    _accept(
        folder,
        PlanDrafted(
            rev=1, overview=overview, plan=plan, slices=(1, 2), gates=("make test", "make lint")
        ),
    )
    state = load_state(folder)
    assert state is not None
    assert state.drafted_gates == ("make test", "make lint")
    assert state.approved_gates is None


def test_an_empty_gates_block_says_the_project_has_none(tmp_path: Path) -> None:
    folder = new_folder(tmp_path, gates=())
    _to_drafting(folder)
    overview, plan = _checked(folder)
    _accept(folder, PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1, 2), gates=()))
    _accept(folder, PlanApproved(rev=1, overview=overview))
    state = load_state(folder)
    assert state is not None
    assert state.approved_gates == ()


def test_a_malformed_gates_block_cannot_be_drafted(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_drafting(folder)
    folder.plan.write_text(plan_text(tail="```gates\nmake\n```\n"), encoding="utf-8")
    overview, plan = _checked(folder)
    refusal = _refusal(
        folder, PlanDrafted(rev=1, overview=overview, plan=plan, slices=(1, 2), gates=None)
    )
    assert refusal.code is RefusalCode.GATE_LIST
    assert "a second gates block" in refusal.reason


def test_approval_takes_the_gates_of_the_drafted_revision(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_awaiting(folder)
    folder.plan.write_text(plan_text(gates=("edited after the draft",)), encoding="utf-8")
    overview = folder.overview_hash()
    assert overview is not None
    _accept(folder, PlanApproved(rev=1, overview=overview))
    state = load_state(folder)
    assert state is not None
    assert state.approved_gates == GATES


def test_an_amendment_during_execution_keeps_the_approved_gates(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    _to_executing(folder)
    folder.plan.write_text(plan_text(gates=("true", "false")), encoding="utf-8")
    plan = folder.plan_hash()
    assert plan is not None
    before = _bytes(folder)
    refusal = _refusal(folder, PlanAmended(slice_=1, why="more gates", plan=plan, slices=(1, 2)))
    assert refusal.code is RefusalCode.GATE_LIST
    assert "only a new revision changes the gates" in refusal.reason
    assert _bytes(folder) == before
    folder.plan.write_text(plan_text(tail="renamed a function\n"), encoding="utf-8")
    plan = folder.plan_hash()
    assert plan is not None
    _accept(folder, PlanAmended(slice_=1, why="renamed", plan=plan, slices=(1, 2)))


def test_a_plan_approved_before_plans_named_their_gates_amends_freely(tmp_path: Path) -> None:
    folder = new_folder(tmp_path, gates=())
    _to_drafting(folder)
    overview, plan = _checked(folder)
    # A journal written before this version: its plan-drafted carries no gates.
    at = timestamp(NOW)
    old = f'"overview": "{overview}", "plan": "{plan}", "slices": [1, 2]'
    with folder.journal.open("a", encoding="utf-8") as journal:
        journal.write(f'{{"v": 1, "at": "{at}", "event": "plan-drafted", "rev": 1, {old}}}\n')
        journal.write(
            f'{{"v": 1, "at": "{at}", "event": "plan-approved", "rev": 1, '
            f'"overview": "{overview}"}}\n'
        )
    state = load_state(folder)
    assert state is not None
    assert state.approved_gates is None
    folder.plan.write_text(plan_text(gates=("make test",)), encoding="utf-8")
    amended = folder.plan_hash()
    assert amended is not None
    _accept(folder, PlanAmended(slice_=1, why="named the gates", plan=amended, slices=(1, 2)))


# The critical-files block of the conformity


def _to_clean_review(folder: PlanFolder) -> str:
    """Drive a plan to a clean review, and return the hash of its overview."""
    _to_executing(folder)
    _accept(folder, SliceDone(slice_=1, gates="lint"))
    _accept(folder, SliceDone(slice_=2, gates="lint"))
    run = folder.next_gate_run()
    write(folder, f"gates/run-{run:02d}.txt")
    _accept(folder, GatesRun(run=run, result=GateResult.PASS))
    report = write(folder, folder.next_review())
    _accept(folder, ReviewDone(pass_=1, report=report, defects=0, deviations=0, breaks=0))
    overview = folder.overview_hash()
    assert overview is not None
    return overview


@pytest.mark.parametrize(
    ("block", "reason"),
    [
        (
            "```critical-files\na.py\n```\n```critical-files\nb.py\n```\n",
            "conformity.md: line 5: a second critical-files block",
        ),
        (
            "```critical-files\nsrc/pay.py\n",
            "conformity.md: line 2: the critical-files block is not closed",
        ),
        (
            "```critical-files\nsrc/pay.py\n/etc/hosts\n```\n",
            "conformity.md: line 4: '/etc/hosts' is not the path of a file inside the repository",
        ),
    ],
)
def test_a_conformity_whose_critical_files_block_is_malformed_is_refused(
    tmp_path: Path, block: str, reason: str
) -> None:
    folder = new_folder(tmp_path)
    overview = _to_clean_review(folder)
    conform = Conform(
        conformity=write(folder, "conformity.md", "proof\n" + block), overview=overview
    )
    before = _bytes(folder)
    refusal = _refusal(folder, conform)
    assert refusal.code is RefusalCode.CRITICAL_FILES
    assert refusal.reason.startswith(reason)
    assert _bytes(folder) == before
    write(folder, "conformity.md", "proof\n```critical-files\nsrc/pay.py\n```\n")
    _accept(folder, conform)


@pytest.mark.parametrize("text", ["proof\n", "proof\n```critical-files\n```\n"])
def test_a_conformity_that_lists_no_critical_file_is_recorded_as_before(
    tmp_path: Path, text: str
) -> None:
    folder = new_folder(tmp_path)
    overview = _to_clean_review(folder)
    assert not parse_critical_files(text)
    _accept(folder, Conform(conformity=write(folder, "conformity.md", text), overview=overview))


def test_a_missing_conformity_is_refused_as_a_missing_file_before_its_block_is_read(
    tmp_path: Path,
) -> None:
    folder = new_folder(tmp_path)
    overview = _to_clean_review(folder)
    refusal = _refusal(folder, Conform(conformity="conformity.md", overview=overview))
    assert refusal.code is RefusalCode.FILE_MISSING


def test_outside_a_git_work_tree_only_the_form_of_the_block_is_checked(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    overview = _to_clean_review(folder)
    text = "proof\n```critical-files\nsrc/pay.py\n```\n"
    conform = Conform(conformity=write(folder, "conformity.md", text), overview=overview)
    result = record(folder, conform, DEFAULTS, NOW, root=tmp_path)
    assert isinstance(result, Accepted), result
