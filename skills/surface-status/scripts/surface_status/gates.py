"""The gate runner: the project's own gates run by the script, so a green result is a fact.

`gate` runs the declared command through `/bin/sh -c` at the project root, in its own process
group, and kills the whole group when the timeout is over (ADR 0017). It writes
`gates/run-NN.txt` (command, exit code, duration, the end of the output), then records `gates-run`
through the same path as every other event, so the guards decide whether the result is accepted.
A run that would be refused is never started: the transition and the ceiling are checked first,
since a gate can take a quarter of an hour.
"""

import contextlib
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from surface_status.events import GateResult, GatesRun
from surface_status.guards import Accepted, RecordContext, Refusal, admit
from surface_status.plan_folder import PlanFolder, gate_run_name
from surface_status.record import load_state, record
from surface_status.settings import Settings

SECONDS_PER_MINUTE = 60
TAIL_LINES = 200
_SHELL = "/bin/sh"


@dataclass(frozen=True, slots=True)
class Execution:
    """What one run of the command left: how it ended, how long it took, the end of its output."""

    result: GateResult
    exit_code: int | None  # None when the run was killed for exceeding the timeout
    seconds: float
    tail: str


@dataclass(frozen=True, slots=True)
class NotDeclared:
    """The project declares no gate command: nothing runs and the gate guards are lifted."""


@dataclass(frozen=True, slots=True)
class NotStarted:
    """The run was refused before it started, for a reason the journal already knows."""

    refusal: Refusal


@dataclass(frozen=True, slots=True)
class Ran:
    """A run that finished, and what the journal made of it."""

    run: int
    report: str  # `gates/run-NN.txt`, relative to the plan folder
    execution: Execution
    recorded: Accepted | Refusal


Outcome = NotDeclared | NotStarted | Ran


def _kill_group(pid: int) -> None:
    """Kill every process the command left in its group, whether or not the shell is gone."""
    with contextlib.suppress(ProcessLookupError):  # nothing of the group may be left
        os.killpg(pid, signal.SIGKILL)


def _tail(output: Path) -> str:
    text = output.read_bytes().decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-TAIL_LINES:])


def execute(command: str, cwd: Path, timeout_seconds: float) -> Execution:
    """Run the command, wait at most `timeout_seconds`, leave no process of its group behind."""
    with tempfile.TemporaryDirectory(prefix="surface-gate-") as scratch:
        output = Path(scratch) / "output"
        started = time.monotonic()
        with output.open("wb") as sink:
            process = subprocess.Popen(  # noqa: S603 (the command is the project's own gate)
                [_SHELL, "-c", command],
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code: int | None = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                code = None
            finally:
                _kill_group(process.pid)
                process.wait()
        seconds = time.monotonic() - started
        if code is None:
            result = GateResult.TIMEOUT
        else:
            result = GateResult.PASS if code == 0 else GateResult.FAIL
        return Execution(result, code, seconds, _tail(output))


def _exit_text(execution: Execution, timeout_seconds: float) -> str:
    code = execution.exit_code
    if code is None:
        return f"none (killed after the timeout of {timeout_seconds:g} seconds)"
    if code < 0:
        return f"{code} (killed by signal {-code})"
    return str(code)


def render_report(command: str, execution: Execution, timeout_seconds: float) -> str:
    """Write the text of `gates/run-NN.txt`."""
    lines = [
        f"command: {command}",
        f"result: {execution.result.value}",
        f"exit code: {_exit_text(execution, timeout_seconds)}",
        f"duration: {execution.seconds:.1f} seconds",
        f"output (last {TAIL_LINES} lines at most):",
        "",
        execution.tail,
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def _write_new(path: Path, text: str) -> None:
    """Create the report; a run number is never reused, so an existing file is an error."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as report:
        report.write(text)


def run_gate(
    folder: PlanFolder,
    root: Path,
    settings: Settings,
    now: datetime,
    timeout_seconds: float | None = None,
) -> Outcome:
    """Run the gates of a plan and record the result; `timeout_seconds` defaults to the setting."""
    command = settings.gate_command
    if command is None:
        return NotDeclared()
    limit = (
        settings.gate_timeout_minutes * SECONDS_PER_MINUTE
        if timeout_seconds is None
        else timeout_seconds
    )
    number = folder.next_gate_run()
    state = load_state(folder)
    # A failed run is the one that counts as a pass, so it is the one asked about: it is refused
    # from a state that takes no gate run and at the ceiling, where a green one would be too.
    context = RecordContext(
        ceiling=settings.max_autonomous_passes,
        gates_declared=True,
        overview_hash=folder.overview_hash(),
    )
    asked = admit(state, GatesRun(run=number, result=GateResult.FAIL), context)
    if isinstance(asked, Refusal):
        return NotStarted(asked)
    execution = execute(command, root, limit)
    name = gate_run_name(number)
    _write_new(folder.path(name), render_report(command, execution, limit))
    recorded = record(folder, GatesRun(run=number, result=execution.result), settings, now)
    return Ran(number, name, execution, recorded)
