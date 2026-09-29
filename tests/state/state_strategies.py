"""Hypothesis strategies that walk the state machine: events biased to be legal, and runs."""

from dataclasses import dataclass
from typing import Any

from hypothesis import strategies as st
from hypothesis.strategies import DrawFn, SearchStrategy
from state_support import EXPECTED, OV1, OV2, PL1, PL2

from surface_status.events import (
    EVENT_NAMES,
    Abandoned,
    AmendmentReceived,
    Blocked,
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
from surface_status.guards import Accepted, RecordContext, admit
from surface_status.machine import PlanState, State

OVERVIEWS = [OV1, OV2]
PLANS = [PL1, PL2]
WORDS = ["a", "b", "c"]


def _mostly(draw: DrawFn, good: Any, other: SearchStrategy[Any]) -> Any:  # noqa: ANN401
    """Draw `good` four times out of five, otherwise anything `other` gives."""
    return good if draw(st.integers(0, 4)) else draw(other)


def _slices(draw: DrawFn, prev: PlanState | None) -> tuple[int, ...]:
    anything = st.frozensets(st.integers(1, 4), max_size=4).map(lambda s: tuple(sorted(s)))
    known = tuple(sorted(prev.declared)) if prev is not None and prev.declared else (1, 2)
    return _mostly(draw, known, anything)  # type: ignore[no-any-return]


def _onward(prev: PlanState | None) -> str | None:  # noqa: C901, PLR0911 (one arm per state)
    """Name the event that moves the plan towards its end, so the walks go deep."""
    if prev is None:
        return "plan-opened"
    match prev.state:
        case State.INTERVIEW:
            return "interview-closed"
        case State.DRAFTING:
            clean = prev.last_check is not None and prev.last_check.omissions == 0
            return "plan-drafted" if clean else "check-done"
        case State.AWAITING_APPROVAL:
            return "plan-approved"
        case State.EXECUTING:
            return "slice-done"
        case State.REVIEWING:
            if prev.gates is not GateResult.PASS:
                return "gates-run"
            if prev.last_review is None:
                return "review-done"
            return "conform" if prev.last_review.clean else "review-done"
        case State.FIXING:
            return "fix-done" if prev.gates is GateResult.PASS else "gates-run"
        case State.BLOCKED:
            return "resumed"
        case State.PLAN_CHANGE_PROPOSED:
            return "plan-change-refused"
        case State.CONFORM | State.ABANDONED:
            return None


@st.composite
def events(draw: DrawFn, prev: PlanState | None) -> Event:  # noqa: C901, PLR0911, PLR0912
    """Draw an event, usually one the table allows from `prev`, with fields that often fit."""
    departure = None if prev is None else prev.state
    legal = [name for name in EVENT_NAMES if departure in EXPECTED[name]]
    if len(legal) > 2 and draw(st.integers(0, 9)):  # these two are rare: abandoning ends a run
        legal = [name for name in legal if name not in {"abandoned", "blocked"}]
    if len(legal) > 1 and draw(st.integers(0, 2)):
        legal = [name for name in legal if name != "abandoned"]
    onward = _onward(prev)
    if onward is not None and draw(st.integers(0, 2)):  # two times out of three, go forward
        legal = [onward]
    name = _mostly(
        draw, draw(st.sampled_from(legal)) if legal else "", st.sampled_from(EVENT_NAMES)
    )
    name = name or draw(st.sampled_from(EVENT_NAMES))
    check = None if prev is None else prev.last_check
    word = st.sampled_from(WORDS)
    match name:
        case "plan-opened":
            return PlanOpened(slug=draw(word))
        case "interview-closed":
            return InterviewClosed()
        case "check-done":
            return CheckDone(
                rev=draw(st.integers(1, 2)),
                report=draw(word),
                omissions=draw(st.sampled_from([0, 0, 0, 0, 0, 1, 2])),
                overview=draw(st.sampled_from(OVERVIEWS)),
                plan=draw(st.sampled_from(PLANS)),
            )
        case "plan-drafted":
            return PlanDrafted(
                rev=_mostly(draw, 1 if check is None else check.rev, st.integers(1, 3)),
                overview=_mostly(
                    draw, OV1 if check is None else check.overview, st.sampled_from(OVERVIEWS)
                ),
                plan=_mostly(draw, PL1 if check is None else check.plan, st.sampled_from(PLANS)),
                slices=_slices(draw, prev),
            )
        case "amendment-received":
            return AmendmentReceived()
        case "plan-approved":
            drafted = None if prev is None else prev.drafted_overview
            return PlanApproved(
                rev=draw(st.integers(1, 3)),
                overview=_mostly(draw, drafted or OV1, st.sampled_from(OVERVIEWS)),
            )
        case "slice-done":
            remaining = () if prev is None else prev.remaining
            good = draw(st.sampled_from(remaining)) if remaining else 1
            return SliceDone(slice_=_mostly(draw, good, st.integers(1, 4)), gates=draw(word))
        case "plan-amended":
            return PlanAmended(
                slice_=draw(st.integers(1, 4)),
                why=draw(word),
                plan=draw(st.sampled_from(PLANS)),
                slices=_slices(draw, prev),
            )
        case "suspicion-dismissed":
            return SuspicionDismissed(slice_=draw(st.integers(1, 4)), report=draw(word))
        case "plan-change-proposed":
            return PlanChangeProposed(proposal=draw(word), slice_=draw(st.integers(1, 4)))
        case "gates-run":
            results = [GateResult.PASS, GateResult.PASS, GateResult.FAIL, GateResult.TIMEOUT]
            return GatesRun(run=draw(st.integers(1, 9)), result=draw(st.sampled_from(results)))
        case "review-done":
            breaks = draw(st.sampled_from([0, 0, 0, 0, 0, 1]))
            proposal = _mostly(draw, draw(word), st.none()) if breaks else None
            return ReviewDone(
                pass_=draw(st.integers(1, 9)),
                report=draw(word),
                defects=draw(st.sampled_from([0, 0, 0, 0, 1, 2])),
                deviations=draw(st.sampled_from([0, 0, 0, 1])),
                breaks=breaks,
                proposal=proposal,
            )
        case "fix-done":
            return FixDone(pass_=draw(st.integers(0, 3)))
        case "plan-change-accepted":
            return PlanChangeAccepted(proposal=draw(word))
        case "plan-change-refused":
            return PlanChangeRefused(proposal=draw(word), why=draw(word))
        case "blocked":
            return Blocked(why=draw(word))
        case "resumed":
            return Resumed()
        case "conform":
            approved = None if prev is None else prev.approved_overview
            return Conform(
                conformity="conformity.md",
                overview=_mostly(draw, approved or OV1, st.sampled_from(OVERVIEWS)),
            )
        case "abandoned":
            return Abandoned(why=draw(word))
        case _:
            message = f"unknown event name {name}"
            raise AssertionError(message)


@st.composite
def contexts(draw: DrawFn, prev: PlanState | None, ceiling: int) -> RecordContext:
    """Draw what the caller read outside the journal, usually consistent with the journal."""
    approved = None if prev is None else prev.approved_overview
    seen = [OV1, OV2, None]
    return RecordContext(
        ceiling=ceiling,
        gates_declared=_mostly(draw, True, st.booleans()),  # noqa: FBT003
        overview_hash=_mostly(draw, approved or OV1, st.sampled_from(seen)),
    )


@dataclass(frozen=True, slots=True)
class Attempt:
    prev: PlanState | None
    event: Event
    context: RecordContext


@dataclass(frozen=True, slots=True)
class Run:
    ceiling: int
    attempts: tuple[Attempt, ...]


@st.composite
def runs(draw: DrawFn) -> Run:
    """Draw a run of attempts to record events, following the state that the accepted ones reach."""
    ceiling = draw(st.integers(1, 4))
    state: PlanState | None = None
    attempts: list[Attempt] = []
    for _ in range(draw(st.integers(1, 60))):
        context = draw(contexts(state, ceiling))
        event = draw(events(state))
        attempts.append(Attempt(state, event, context))
        result = admit(state, event, context)
        if isinstance(result, Accepted):
            state = result.state
    return Run(ceiling, tuple(attempts))
