"""Build an event from what a caller passes: judgments only (ADR 0012).

`record` on the command line takes counts, reasons, results and the paths of the reports the
caller wrote. Everything else is derived here from the journal and the plan folder: the revision,
the hashes, the slice list, the gates, the pass numbers, the pending proposal. A caller cannot pass
a derived value, so it cannot record a wrong one.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from surface_status.events import (
    Abandoned,
    AmendmentReceived,
    Blocked,
    BreakSuspected,
    CheckDone,
    Conform,
    Event,
    FixDone,
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
from surface_status.guards import Refusal, RefusalCode
from surface_status.machine import PlanState
from surface_status.plan_folder import OVERVIEW, PLAN, PlanFolder, PlanFolderError

_DATE_PREFIX = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}-")

# Recorded by the gate runner, which runs the gates and keeps their exit code: a caller that could
# record a result would be declaring a success it has not verified (ADR 0017).
GATE_EVENT = "gates-run"


class Kind(StrEnum):
    LINE = "line"  # one non-empty line of text
    PATH = "path"  # a file of the plan folder, relative to it
    COUNT = "count"  # a whole number of at least 0
    SLICE = "slice"  # a whole number of at least 1


@dataclass(frozen=True, slots=True)
class Param:
    """One field a caller passes, as the option `--<key>`."""

    key: str
    kind: Kind
    help: str
    required: bool = True


# The fields a caller passes, per event, in the order of the list of events.
PARAMS: Mapping[str, tuple[Param, ...]] = {
    "plan-opened": (
        Param(
            "slug",
            Kind.LINE,
            "name of the plan; the folder name without its date",
            required=False,
        ),
    ),
    "interview-closed": (),
    "check-done": (
        Param("report", Kind.PATH, "the cross-check report, like checks/rev-01-01.md"),
        Param("omissions", Kind.COUNT, "how many omissions the report counts"),
    ),
    "plan-drafted": (),
    "amendment-received": (),
    "plan-approved": (),
    "slice-done": (
        Param("slice", Kind.SLICE, "the slice that is done"),
        Param("gates", Kind.LINE, "the gates the executor ran, on one line"),
    ),
    "plan-amended": (
        Param("slice", Kind.SLICE, "the slice that deviated"),
        Param("why", Kind.LINE, "the reason, on one line"),
    ),
    "break-suspected": (
        Param("slice", Kind.SLICE, "the slice during which the break is suspected"),
        Param("why", Kind.LINE, "the reason, on one line"),
    ),
    "suspicion-dismissed": (
        Param("slice", Kind.SLICE, "the slice under suspicion"),
        Param("report", Kind.PATH, "the reviewer's note, like reviews/suspicion-01.md"),
    ),
    "plan-change-proposed": (
        Param("proposal", Kind.PATH, "the proposal, like plan-changes/01.md"),
        Param("slice", Kind.SLICE, "the slice during which the break was suspected"),
    ),
    "review-done": (
        Param("report", Kind.PATH, "the review report, like reviews/pass-01.md"),
        Param("defects", Kind.COUNT, "how many defects it counts"),
        Param("deviations", Kind.COUNT, "how many deviations it counts"),
        Param("breaks", Kind.COUNT, "how many breaks it counts"),
        Param(
            "proposal", Kind.PATH, "the plan change proposal, required on a break", required=False
        ),
    ),
    "fix-done": (),
    "plan-change-accepted": (),
    "plan-change-refused": (Param("why", Kind.LINE, "the reason, on one line"),),
    "blocked": (Param("why", Kind.LINE, "the reason, on one line"),),
    "resumed": (),
    "conform": (Param("conformity", Kind.PATH, "the proof of conformity, conformity.md"),),
    "abandoned": (Param("why", Kind.LINE, "the reason, on one line"),),
}


def default_slug(folder: PlanFolder) -> str:
    """Return the folder name without its date, `2026-09-29-feature` giving `feature`."""
    return _DATE_PREFIX.sub("", folder.name, count=1)


def current_revision(events: Sequence[Event]) -> int:
    """Return the revision of the plan being drafted: 1, plus one per restart of the draft.

    The draft restarts on an amendment of the developer and on an accepted plan change.
    """
    restarts = sum(isinstance(event, AmendmentReceived | PlanChangeAccepted) for event in events)
    return 1 + restarts


def next_review_pass(events: Sequence[Event]) -> int:
    return 1 + sum(isinstance(event, ReviewDone) for event in events)


def _missing(*names: str) -> Refusal:
    return Refusal(RefusalCode.FILE_MISSING, "cited file missing: " + ", ".join(names))


def _text(values: Mapping[str, object], key: str) -> str:
    return str(values[key])


def _number(values: Mapping[str, object], key: str) -> int:
    value = values[key]
    if type(value) is not int:
        message = f"{key} must be a whole number"
        raise TypeError(message)
    return value


def build_event(  # noqa: C901, PLR0911, PLR0912 (one arm per event)
    name: str,
    values: Mapping[str, object],
    folder: PlanFolder,
    events: Sequence[Event],
    state: PlanState | None,
) -> Event | Refusal:
    """Return the event, or the refusal of a derived value that cannot be had.

    `values` holds the parameters of `PARAMS[name]` that the caller gave. A file a derived hash
    needs and that does not exist is refused the way the disk guards refuse it.
    """
    overview = folder.overview_hash()
    plan = folder.plan_hash()
    match name:
        case "plan-opened":
            return PlanOpened(
                slug=_text(values, "slug") if "slug" in values else default_slug(folder)
            )
        case "interview-closed":
            return InterviewClosed()
        case "check-done":
            if overview is None or plan is None:
                return _missing(*(n for n, h in ((OVERVIEW, overview), (PLAN, plan)) if h is None))
            return CheckDone(
                rev=current_revision(events),
                report=_text(values, "report"),
                omissions=_number(values, "omissions"),
                overview=overview,
                plan=plan,
            )
        case "plan-drafted":
            if overview is None or plan is None:
                return _missing(*(n for n, h in ((OVERVIEW, overview), (PLAN, plan)) if h is None))
            try:
                slices = folder.declared_slices()
            except PlanFolderError:
                slices = ()  # the disk guards refuse it, with the reason
            try:
                gates = folder.declared_gates()
            except PlanFolderError:
                gates = None  # the disk guards refuse it, with the reason
            return PlanDrafted(
                rev=current_revision(events),
                overview=overview,
                plan=plan,
                slices=slices,
                gates=gates,
            )
        case "amendment-received":
            return AmendmentReceived()
        case "plan-approved":
            if overview is None:
                return _missing(OVERVIEW)
            return PlanApproved(rev=current_revision(events), overview=overview)
        case "slice-done":
            return SliceDone(slice_=_number(values, "slice"), gates=_text(values, "gates"))
        case "plan-amended":
            if plan is None:
                return _missing(PLAN)
            try:
                slices = folder.declared_slices()
            except PlanFolderError:
                slices = ()
            return PlanAmended(
                slice_=_number(values, "slice"),
                why=_text(values, "why"),
                plan=plan,
                slices=slices,
            )
        case "break-suspected":
            return BreakSuspected(slice_=_number(values, "slice"), why=_text(values, "why"))
        case "suspicion-dismissed":
            return SuspicionDismissed(
                slice_=_number(values, "slice"), report=_text(values, "report")
            )
        case "plan-change-proposed":
            return PlanChangeProposed(
                proposal=_text(values, "proposal"), slice_=_number(values, "slice")
            )
        case "review-done":
            return ReviewDone(
                pass_=next_review_pass(events),
                report=_text(values, "report"),
                defects=_number(values, "defects"),
                deviations=_number(values, "deviations"),
                breaks=_number(values, "breaks"),
                proposal=_text(values, "proposal") if "proposal" in values else None,
            )
        case "fix-done":
            review = None if state is None else state.last_review
            return FixDone(pass_=0 if review is None else review.pass_)
        case "plan-change-accepted" | "plan-change-refused":
            pending = None if state is None else state.pending_proposal
            if pending is None:
                return Refusal(RefusalCode.TRANSITION, "no plan change proposal is pending")
            if name == "plan-change-accepted":
                return PlanChangeAccepted(proposal=pending)
            return PlanChangeRefused(proposal=pending, why=_text(values, "why"))
        case "blocked":
            return Blocked(why=_text(values, "why"))
        case "resumed":
            return Resumed()
        case "conform":
            if overview is None:
                return _missing(OVERVIEW)
            return Conform(conformity=_text(values, "conformity"), overview=overview)
        case "abandoned":
            return Abandoned(why=_text(values, "why"))
        case _:
            message = f"no builder for the event {name!r}"
            raise LookupError(message)
