"""Shared builders for the command line tests: a project on disk, and the CLI run in process."""

import io
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from surface_status.cli import main

FIXED_NOW = datetime(2026, 9, 29, 9, 0, 0, tzinfo=UTC)
GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "cli"
PLAN = "2026-09-29-feature"

# The states a constructed plan can be driven to, by the events of the way there.
_TO_INTERVIEW = (("plan-opened", ()),)
_TO_DRAFTING = (*_TO_INTERVIEW, ("interview-closed", ()))
_TO_AWAITING = (
    *_TO_DRAFTING,
    ("check-done", ("--report", "checks/rev-01-01.md", "--omissions", "0")),
    ("plan-drafted", ()),
)
_TO_EXECUTING = (*_TO_AWAITING, ("plan-approved", ()))
_TO_REVIEWING = (
    *_TO_EXECUTING,
    ("slice-done", ("--slice", "1", "--gates", "lint")),
    ("slice-done", ("--slice", "2", "--gates", "lint")),
)
_TO_PLAN_CHANGE_PROPOSED = (
    *_TO_EXECUTING,
    ("plan-change-proposed", ("--proposal", "plan-changes/01.md", "--slice", "1")),
)
_TO_CONFORM = (
    *_TO_REVIEWING,
    (
        "review-done",
        ("--report", "reviews/pass-01.md", "--defects", "0", "--deviations", "0", "--breaks", "0"),
    ),
    ("conform", ("--conformity", "conformity.md")),
)
WAYS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "interview": _TO_INTERVIEW,
    "drafting": _TO_DRAFTING,
    "awaiting-approval": _TO_AWAITING,
    "executing": _TO_EXECUTING,
    "reviewing": _TO_REVIEWING,
    "plan-change-proposed": _TO_PLAN_CHANGE_PROPOSED,
    "conform": _TO_CONFORM,
}
REPORTS = ("checks/rev-01-01.md", "reviews/pass-01.md", "plan-changes/01.md", "conformity.md")


def plan_text(gates: tuple[str, ...]) -> str:
    """Write a `plan.md` of two slices whose gates block names `gates`."""
    block = "".join(f"{command}\n" for command in gates)
    return f"<!-- slice:1 -->\n<!-- slice:2 -->\n```gates\n{block}```\n"


@dataclass(frozen=True, slots=True)
class Result:
    code: int
    out: str
    err: str

    def json(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(self.out)
        return loaded


class Project:
    """A host project in a temporary folder, driven through `main` with a fixed clock."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.plans = root / "docs" / "plans"
        self.plans.mkdir(parents=True)

    def run(self, *args: str, as_json: bool = True) -> Result:
        out, err = io.StringIO(), io.StringIO()
        argv = ["--root", str(self.root), *(["--json"] if as_json else []), *args]
        code = main(argv, now=lambda: FIXED_NOW, cwd=self.root, stdout=out, stderr=err)
        return Result(code, out.getvalue(), err.getvalue())

    def plan(self, name: str = PLAN, gates: tuple[str, ...] = ()) -> Path:
        """Make a plan folder holding the developer's files: a blueprint, a plan of two slices.

        The plan names `gates` in its gates block; none by default, so the gate guards are lifted.
        """
        folder = self.plans / name
        folder.mkdir()
        (folder / "blueprint.md").write_text("# Blueprint\n", encoding="utf-8")
        (folder / "plan.md").write_text(plan_text(gates), encoding="utf-8")
        return folder

    def record(self, plan: str, event: str, *args: str) -> Result:
        return self.run("record", plan, event, *args)

    def reach(self, state: str, name: str = PLAN, gates: tuple[str, ...] = ()) -> Path:
        """Make a plan and drive it to a state through the command line, as an agent would."""
        folder = self.plan(name, gates)
        for report in REPORTS:
            target = folder / report
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("report\n", encoding="utf-8")
        for event, args in WAYS[state]:
            result = self.record(name, event, *args)
            assert result.code == 0, (event, result)
        return folder

    def journal(self, name: str = PLAN) -> bytes:
        path = self.plans / name / "journal.jsonl"
        return path.read_bytes() if path.exists() else b""


def assert_golden(name: str, actual: str) -> None:
    """Compare with a golden file; `UPDATE_GOLDEN=1` rewrites it, and the diff is then reviewed."""
    path = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(actual, encoding="utf-8")
    assert actual == path.read_text(encoding="utf-8"), name
