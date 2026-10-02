"""The closed list of journal events, as frozen dataclasses.

A journal line is `v`, `at`, `event` plus the own fields of the event (ADR 0012). `v` and
`at` belong to the line, not to the event: the codec adds and strips them, so the pure core never
sees a date. An attribute named `x_` stands for the journal key `x`, for the two keys that clash
with Python (`pass`, `slice`).

Every hash is the `sha256:` string the script computes, every path is relative to the plan folder.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, TypeAlias


class GateResult(StrEnum):
    PASS = "pass"  # noqa: S105 (a gate result, not a password)
    FAIL = "fail"
    TIMEOUT = "timeout"  # a timeout is a failure


@dataclass(frozen=True, slots=True)
class PlanOpened:
    name: ClassVar[str] = "plan-opened"
    slug: str


@dataclass(frozen=True, slots=True)
class InterviewClosed:
    name: ClassVar[str] = "interview-closed"


@dataclass(frozen=True, slots=True)
class CheckDone:
    name: ClassVar[str] = "check-done"
    rev: int
    report: str
    omissions: int
    blueprint: str
    plan: str


@dataclass(frozen=True, slots=True)
class PlanDrafted:
    name: ClassVar[str] = "plan-drafted"
    rev: int
    blueprint: str
    plan: str
    slices: tuple[int, ...]
    # The commands of the `gates` block of `plan.md`, which the gate runner runs once this
    # revision is approved. None only in a journal written before plans named their gates.
    gates: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class AmendmentReceived:
    name: ClassVar[str] = "amendment-received"


@dataclass(frozen=True, slots=True)
class PlanApproved:
    name: ClassVar[str] = "plan-approved"
    rev: int
    blueprint: str


@dataclass(frozen=True, slots=True)
class SliceDone:
    name: ClassVar[str] = "slice-done"
    slice_: int
    gates: str  # one line: the gates the executor ran for this slice


@dataclass(frozen=True, slots=True)
class PlanAmended:
    name: ClassVar[str] = "plan-amended"
    slice_: int
    why: str
    plan: str
    slices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BreakSuspected:
    name: ClassVar[str] = "break-suspected"
    slice_: int
    why: str  # one line: the executor's reason, kept until a reviewer judges it


@dataclass(frozen=True, slots=True)
class SuspicionDismissed:
    name: ClassVar[str] = "suspicion-dismissed"
    slice_: int
    report: str


@dataclass(frozen=True, slots=True)
class PlanChangeProposed:
    name: ClassVar[str] = "plan-change-proposed"
    proposal: str
    slice_: int


@dataclass(frozen=True, slots=True)
class GatesRun:
    name: ClassVar[str] = "gates-run"
    run: int
    result: GateResult


@dataclass(frozen=True, slots=True)
class ReviewDone:
    name: ClassVar[str] = "review-done"
    pass_: int
    report: str
    defects: int
    deviations: int
    breaks: int
    proposal: str | None = None  # required when `breaks` is above zero


@dataclass(frozen=True, slots=True)
class FixDone:
    name: ClassVar[str] = "fix-done"
    pass_: int  # number of the last review, 0 if there was none


@dataclass(frozen=True, slots=True)
class PlanChangeAccepted:
    name: ClassVar[str] = "plan-change-accepted"
    proposal: str


@dataclass(frozen=True, slots=True)
class PlanChangeRefused:
    name: ClassVar[str] = "plan-change-refused"
    proposal: str
    why: str


@dataclass(frozen=True, slots=True)
class Blocked:
    name: ClassVar[str] = "blocked"
    why: str


@dataclass(frozen=True, slots=True)
class Resumed:
    name: ClassVar[str] = "resumed"


@dataclass(frozen=True, slots=True)
class Conformant:
    name: ClassVar[str] = "conformant"
    conformity: str
    blueprint: str


@dataclass(frozen=True, slots=True)
class Abandoned:
    name: ClassVar[str] = "abandoned"
    why: str


Event: TypeAlias = (
    PlanOpened
    | InterviewClosed
    | CheckDone
    | PlanDrafted
    | AmendmentReceived
    | PlanApproved
    | SliceDone
    | PlanAmended
    | BreakSuspected
    | SuspicionDismissed
    | PlanChangeProposed
    | GatesRun
    | ReviewDone
    | FixDone
    | PlanChangeAccepted
    | PlanChangeRefused
    | Blocked
    | Resumed
    | Conformant
    | Abandoned
)

# In a fixed order, which the exhaustive tests follow.
EVENT_TYPES: tuple[type[Event], ...] = (
    PlanOpened,
    InterviewClosed,
    CheckDone,
    PlanDrafted,
    AmendmentReceived,
    PlanApproved,
    SliceDone,
    PlanAmended,
    BreakSuspected,
    SuspicionDismissed,
    PlanChangeProposed,
    GatesRun,
    ReviewDone,
    FixDone,
    PlanChangeAccepted,
    PlanChangeRefused,
    Blocked,
    Resumed,
    Conformant,
    Abandoned,
)
EVENT_NAMES: tuple[str, ...] = tuple(kind.name for kind in EVENT_TYPES)
