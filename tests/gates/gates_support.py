"""Shared builders for the gate runner tests: a plan that names its gates."""

import json
import subprocess
import time
from pathlib import Path

from cli_support import PLAN, Project

from surface_status.plan_folder import gate_run_name

# One "minute" lasts this many seconds in the tests, so a timeout of one minute is a blink.
SHORT_MINUTE = 0.3


def configure(project: Project, **settings: object) -> None:
    """Write `.claude/surface.json` with these settings."""
    path = project.root / ".claude" / "surface.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(settings), encoding="utf-8")


def reviewing(project: Project, *commands: str, **settings: object) -> Path:
    """Build a plan whose slices are done, in `reviewing`, approved with these gates."""
    if settings:
        configure(project, **settings)
    return project.reach("reviewing", gates=commands)


def events(project: Project) -> list[dict[str, object]]:
    lines = project.journal().decode("utf-8").splitlines()
    return [json.loads(line) for line in lines]


def run_report(project: Project, n: int = 1) -> str:
    return (project.plans / PLAN / gate_run_name(n)).read_text(encoding="utf-8")


def alive(pid: int) -> bool:
    """Whether a process still runs; a zombie waiting to be reaped does not count."""
    done = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],  # noqa: S607 (ps is looked up on the PATH)
        capture_output=True,
        text=True,
        check=False,
    )
    state = done.stdout.strip()
    return bool(state) and not state.startswith("Z")


def wait_gone(pid: int, seconds: float = 3.0) -> bool:
    """Whether the process is gone within the delay (the kernel reaps an orphan a moment later)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(0.02)
    return not alive(pid)
