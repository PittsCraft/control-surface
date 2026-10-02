"""Shared builders for the journal tests: a strategy over every valid event, a plan folder."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from surface_status.events import (
    Abandoned,
    AmendmentReceived,
    Blocked,
    BreakSuspected,
    CheckDone,
    Conform,
    Event,
    FixDone,
    GateResult,
    GatesRun,
    InterviewClosed,
    PlanAmended,
    PlanApproved,
    PlanChangeAccepted,
    PlanChangeProposed,
    PlanChangeRefused,
    PlanDrafted,
    PlanOpened,
    Resumed,
    ReviewDone,
    SliceDone,
    SuspicionDismissed,
)
from surface_status.journal import TIMESTAMP_FORMAT, JournalLine
from surface_status.machine import PlanState, State
from surface_status.plan_folder import (
    PlanFolder,
    gate_run_name,
    plan_change_name,
)
from surface_status.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "journals"
NOW = datetime(2026, 9, 29, 9, 0, 0, tzinfo=UTC)

_texts = st.text(max_size=12)
_counts = st.integers(0, 10**6)
_slice = st.integers(1, 10**4)
_hashes = st.binary(max_size=6).map(lambda data: "sha256:" + sha256(data).hexdigest())
_slices = st.lists(_slice, unique=True, max_size=6).map(tuple)
_commands = st.lists(st.text(min_size=1, max_size=12), max_size=3).map(tuple)

# The gates block every plan of these tests names, unless a test says otherwise.
GATES = ("true",)

# What a reviewer may leave in `conformity.md`: no list of files to read, one the script can
# read, and two it cannot, a path that leaves the repository and a block that is never closed.
CONFORMITIES = (
    "report\n",
    "report\n```critical-files\nsrc/pay.py\n```\n",
    "report\n```critical-files\n../pay.py\n```\n",
    "report\n```critical-files\nsrc/pay.py\n",
)

EVENTS: dict[type[Event], SearchStrategy[Event]] = {
    PlanOpened: st.builds(PlanOpened, slug=_texts),
    InterviewClosed: st.builds(InterviewClosed),
    CheckDone: st.builds(
        CheckDone, rev=_counts, report=_texts, omissions=_counts, blueprint=_hashes, plan=_hashes
    ),
    PlanDrafted: st.builds(
        PlanDrafted,
        rev=_counts,
        blueprint=_hashes,
        plan=_hashes,
        slices=_slices,
        gates=st.none() | _commands,
    ),
    AmendmentReceived: st.builds(AmendmentReceived),
    PlanApproved: st.builds(PlanApproved, rev=_counts, blueprint=_hashes),
    SliceDone: st.builds(SliceDone, slice_=_slice, gates=_texts),
    PlanAmended: st.builds(PlanAmended, slice_=_slice, why=_texts, plan=_hashes, slices=_slices),
    BreakSuspected: st.builds(BreakSuspected, slice_=_slice, why=_texts),
    SuspicionDismissed: st.builds(SuspicionDismissed, slice_=_slice, report=_texts),
    PlanChangeProposed: st.builds(PlanChangeProposed, proposal=_texts, slice_=_slice),
    GatesRun: st.builds(GatesRun, run=_counts, result=st.sampled_from(GateResult)),
    ReviewDone: st.builds(
        ReviewDone,
        pass_=_counts,
        report=_texts,
        defects=_counts,
        deviations=_counts,
        breaks=_counts,
        proposal=st.none() | _texts,
    ),
    FixDone: st.builds(FixDone, pass_=_counts),
    PlanChangeAccepted: st.builds(PlanChangeAccepted, proposal=_texts),
    PlanChangeRefused: st.builds(PlanChangeRefused, proposal=_texts, why=_texts),
    Blocked: st.builds(Blocked, why=_texts),
    Resumed: st.builds(Resumed),
    Conform: st.builds(Conform, conformity=_texts, blueprint=_hashes),
    Abandoned: st.builds(Abandoned, why=_texts),
}
all_events = st.one_of(list(EVENTS.values()))

_FIRST, _LAST = datetime(2000, 1, 1), datetime(2100, 1, 1)  # noqa: DTZ001 (the format fixes the zone)
at_times = st.datetimes(min_value=_FIRST, max_value=_LAST).map(
    lambda moment: moment.strftime(TIMESTAMP_FORMAT)
)
journal_lines = st.builds(JournalLine, at=at_times, event=all_events)


def plan_text(
    slices: tuple[int, ...] = (1, 2), gates: tuple[str, ...] | None = GATES, tail: str = ""
) -> str:
    """Write the text of a `plan.md`: its slice markers, then its gates block unless None."""
    text = "".join(f"<!-- slice:{n} -->\n" for n in slices)
    if gates is not None:
        text += "```gates\n" + "".join(f"{command}\n" for command in gates) + "```\n"
    return text + tail


def new_folder(
    parent: Path, name: str = "2026-09-29-feature", gates: tuple[str, ...] = GATES
) -> PlanFolder:
    """Make a plan folder holding the developer's files: a blueprint, a plan of two slices."""
    root = parent / name
    root.mkdir()
    folder = PlanFolder(root)
    folder.blueprint.write_text("# Blueprint\n", encoding="utf-8")
    folder.plan.write_text(plan_text(gates=gates), encoding="utf-8")
    return folder


def write(folder: PlanFolder, relative: str, text: str = "report\n") -> str:
    path = folder.path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return relative


def make_event(  # noqa: C901, PLR0911, PLR0912 (one arm per event)
    name: str, folder: PlanFolder, state: PlanState | None, data: st.DataObject
) -> Event:
    """Build an event the way the script will: hashes and numbers from the disk, files written.

    Judgments (counts, results) are drawn, and now and then a value is left stale, so the walks
    meet both acceptances and refusals of every guard.
    """
    blueprint = folder.blueprint_hash() or ""
    plan = folder.plan_hash() or ""
    slices = folder.declared_slices()
    review = state.last_review if state else None
    check = state.last_check if state else None
    suspected = state.suspicion.slice_ if state and state.suspicion else 1
    match name:
        case "plan-opened":
            return PlanOpened(slug=folder.name)
        case "interview-closed":
            return InterviewClosed()
        case "check-done":
            rev = data.draw(st.integers(1, 2))
            report = write(folder, folder.next_check(rev))
            omissions = data.draw(st.sampled_from([0, 0, 0, 1]))
            return CheckDone(
                rev=rev, report=report, omissions=omissions, blueprint=blueprint, plan=plan
            )
        case "plan-drafted":
            return PlanDrafted(
                rev=check.rev if check else 1,
                blueprint=blueprint,
                plan=plan,
                slices=slices,
                gates=folder.declared_gates(),
            )
        case "amendment-received":
            return AmendmentReceived()
        case "plan-approved":
            return PlanApproved(rev=1, blueprint=blueprint)
        case "slice-done":
            pending = state.remaining if state and state.remaining else (1, 2)
            return SliceDone(slice_=data.draw(st.sampled_from(pending)), gates="lint")
        case "plan-amended":
            return PlanAmended(slice_=1, why="renamed", plan=plan, slices=slices)
        case "break-suspected":
            pending = state.remaining if state and state.remaining else (1, 2)
            return BreakSuspected(slice_=data.draw(st.sampled_from(pending)), why="a new field")
        case "suspicion-dismissed":
            report = write(folder, folder.next_suspicion())
            return SuspicionDismissed(slice_=suspected, report=report)
        case "plan-change-proposed":
            change = write(folder, folder.next_plan_change())
            return PlanChangeProposed(proposal=change, slice_=suspected)
        case "gates-run":
            run = folder.next_gate_run()
            write(folder, gate_run_name(run))
            return GatesRun(run=run, result=data.draw(st.sampled_from(GateResult)))
        case "review-done":
            report = write(folder, folder.next_review())
            defects, deviations, breaks = (data.draw(st.sampled_from([0, 0, 1])) for _ in range(3))
            proposal = write(folder, folder.next_plan_change()) if breaks else None
            return ReviewDone(
                pass_=int(report.split("-")[-1].removesuffix(".md")),
                report=report,
                defects=defects,
                deviations=deviations,
                breaks=breaks,
                proposal=proposal,
            )
        case "fix-done":
            return FixDone(pass_=review.pass_ if review else 0)
        case "plan-change-accepted":
            return PlanChangeAccepted(proposal=_pending(state))
        case "plan-change-refused":
            return PlanChangeRefused(proposal=_pending(state), why="not wanted")
        case "blocked":
            return Blocked(why="does not converge")
        case "resumed":
            return Resumed()
        case "conform":
            text = data.draw(st.sampled_from(CONFORMITIES))
            return Conform(conformity=write(folder, "conformity.md", text), blueprint=blueprint)
        case "abandoned":
            return Abandoned(why="changed my mind")
        case _:
            message = f"unknown event {name}"
            raise ValueError(message)


def onward(state: PlanState | None) -> str | None:  # noqa: C901, PLR0911 (one arm per state)
    """Name the event that moves a plan towards its end, so that the walks go deep."""
    if state is None:
        return "plan-opened"
    match state.state:
        case State.INTERVIEW:
            return "interview-closed"
        case State.DRAFTING:
            clean = state.last_check is not None and state.last_check.omissions == 0
            return "plan-drafted" if clean else "check-done"
        case State.AWAITING_APPROVAL:
            return "plan-approved"
        case State.EXECUTING:
            return "slice-done" if state.suspicion is None else "suspicion-dismissed"
        case State.REVIEWING:
            if state.gates is not GateResult.PASS:
                return "gates-run"
            clean_review = state.last_review is not None and state.last_review.clean
            return "conform" if clean_review else "review-done"
        case State.FIXING:
            return "fix-done" if state.gates is GateResult.PASS else "gates-run"
        case State.BLOCKED:
            return "resumed"
        case State.PLAN_CHANGE_PROPOSED:
            return "plan-change-refused"
        case State.CONFORM | State.ABANDONED:
            return None


def _pending(state: PlanState | None) -> str:
    return state.pending_proposal if state and state.pending_proposal else plan_change_name(1)


def settings_with(ceiling: int) -> Settings:
    return Settings(max_autonomous_passes=ceiling)
