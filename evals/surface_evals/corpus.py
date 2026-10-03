"""The corpus: needs on the synthetic host, each with what the agents never see.

A case is a folder of `evals/cases/`: the need the developer types, the brief of what they know
and did not write, the acceptance tests of the delivered code, a reference implementation that
proves those tests fair, and `case.json`, what a good run of this need looks like.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from surface_evals import CASES, HOST

# The shapes the corpus is chosen for: each calls for another cut of the blueprint, another
# interview, another path through the loop.
SHAPES = (
    "one-behavior",
    "several-flows",
    "across-components",
    "trade-off",
    "critical-zone",
    "ambiguous",
)
KEYS = (
    "shape",
    "summary",
    "body_sections",
    "diagram",
    "critical_zones",
    "critical_files",
    "amendment",
)
_RAN = re.compile(r"^Ran (?P<ran>[0-9]+) tests?", re.MULTILINE)
_FAILED = re.compile(r"(?P<kind>failures|errors)=(?P<count>[0-9]+)")


class CaseError(ValueError):
    pass


class Diagram(StrEnum):
    """Whether the feature has a shape that prose flattens."""

    NONE = "none"
    SOME = "some"
    EITHER = "either"


@dataclass(frozen=True, slots=True)
class Case:
    root: Path
    shape: str
    summary: str
    body_sections: tuple[int, int]  # the fewest and the most sections a good cut would have
    diagram: Diagram
    critical_zones: tuple[str, ...]  # key phrases of the declared zones the feature touches
    critical_files: tuple[str, ...]  # the files of those zones it must change
    amendment: str | None  # what the developer asks for after reading the blueprint

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def need(self) -> str:
        return (self.root / "need.md").read_text(encoding="utf-8").strip()

    @property
    def brief(self) -> str:
        return (self.root / "brief.md").read_text(encoding="utf-8").strip()

    @property
    def acceptance(self) -> Path:
        return self.root / "acceptance"

    @property
    def reference(self) -> Path:
        return self.root / "reference"


@dataclass(frozen=True, slots=True)
class Acceptance:
    """The acceptance tests run on a project: how many ran, and how many did not pass."""

    ran: int
    failed: int
    output: str

    @property
    def passed(self) -> int:
        return self.ran - self.failed

    @property
    def ok(self) -> bool:
        return self.ran > 0 and self.failed == 0


def _texts(name: str, key: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in cast("list[object]", value)
    ):
        message = f"{name}: {key} must be a list of texts"
        raise CaseError(message)
    return tuple(cast("list[str]", value))


def _sections(name: str, value: object) -> tuple[int, int]:
    bounds = cast("dict[str, object]", value) if isinstance(value, dict) else {}
    low, high = bounds.get("min"), bounds.get("max")
    if type(low) is not int or type(high) is not int or not 1 <= low <= high:
        message = f"{name}: body_sections must hold a min and a max, 1 <= min <= max"
        raise CaseError(message)
    return low, high


def load_case(root: Path) -> Case:
    """Read a case folder, refusing one that is not whole: a missing piece would skew a run."""
    name = root.name
    try:
        raw = cast("dict[str, object]", json.loads((root / "case.json").read_text("utf-8")))
    except (OSError, ValueError) as error:
        message = f"{name}: case.json cannot be read: {error}"
        raise CaseError(message) from error
    if tuple(raw) != KEYS:
        message = f"{name}: case.json must hold exactly the keys {', '.join(KEYS)}, in that order"
        raise CaseError(message)
    if raw["shape"] not in SHAPES:
        message = f"{name}: unknown shape {raw['shape']!r}; known: {', '.join(SHAPES)}"
        raise CaseError(message)
    amendment = raw["amendment"]
    if amendment is not None and not isinstance(amendment, str):
        message = f"{name}: amendment must be a text or null"
        raise CaseError(message)
    for piece in ("need.md", "brief.md", "acceptance/test_acceptance.py"):
        if not (root / piece).is_file():
            message = f"{name}: {piece} is missing"
            raise CaseError(message)
    if not (root / "reference").is_dir():
        message = f"{name}: the reference implementation is missing"
        raise CaseError(message)
    try:
        diagram = Diagram(str(raw["diagram"]))
    except ValueError as error:
        message = f"{name}: diagram must be one of {', '.join(Diagram)}"
        raise CaseError(message) from error
    return Case(
        root=root,
        shape=str(raw["shape"]),
        summary=str(raw["summary"]),
        body_sections=_sections(name, raw["body_sections"]),
        diagram=diagram,
        critical_zones=_texts(name, "critical_zones", raw["critical_zones"]),
        critical_files=_texts(name, "critical_files", raw["critical_files"]),
        amendment=amendment,
    )


def load_cases(names: Sequence[str] = ()) -> list[Case]:
    """Read the cases named, or the whole corpus, in the order of their folders."""
    known = sorted(path for path in CASES.iterdir() if (path / "case.json").is_file())
    if not names:
        return [load_case(path) for path in known]
    by_name = {path.name: path for path in known}
    missing = [name for name in names if name not in by_name]
    if missing:
        message = f"unknown case {missing[0]!r}; known: {', '.join(by_name)}"
        raise CaseError(message)
    return [load_case(by_name[name]) for name in names]


def copy_host(project: Path) -> None:
    """Copy the synthetic host as the files of a project."""
    shutil.copytree(HOST, project, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)


def apply_reference(case: Case, project: Path) -> None:
    """Lay the reference implementation of a case over a project."""
    shutil.copytree(
        case.reference,
        project,
        ignore=shutil.ignore_patterns("__pycache__"),
        dirs_exist_ok=True,
    )


def run_acceptance(case: Case, project: Path) -> Acceptance:
    """Run the acceptance tests of a case on a project, from a copy the project never holds."""
    with tempfile.TemporaryDirectory() as scratch:
        tests = Path(scratch) / "acceptance"
        shutil.copytree(case.acceptance, tests, ignore=shutil.ignore_patterns("__pycache__"))
        done = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-t", str(tests)],
            cwd=project,
            env={**os.environ, "LENDING_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    output = done.stderr + done.stdout
    ran = _RAN.search(output)
    failed = sum(int(found["count"]) for found in _FAILED.finditer(output))
    if ran is None:
        return Acceptance(ran=0, failed=0, output=output)
    return Acceptance(ran=int(ran["ran"]), failed=failed, output=output)
