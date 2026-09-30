"""The gate runner: the project's own gates run by the script, so a green result is a fact.

The gates are the commands of the `gates` block of the approved revision of the plan, as its
`plan-drafted` recorded them (ADR 0034): an edit of `plan.md` after the approval does not change
what runs. `gate` runs them in order, each through `/bin/sh -c` at the project root, in its own
process group, and stops at the first that fails. The whole run has a fixed timeout; the group of
the command running when it expires is killed. It writes one report, `gates/run-NN.txt`, then
records `gates-run` through the same path as every other event, so the guards decide whether the
result is accepted. A run that would be refused is never started: the transition and the ceiling
are checked first, since a gate can take a quarter of an hour. The report is committed in the plan
folder, so it names the project root `.` and the home directory `~`: no path of the machine
reaches it.
"""

import contextlib
import os
import re
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from surface_status.events import GateResult, GatesRun
from surface_status.guards import Accepted, Refusal, admit
from surface_status.plan_folder import PlanFolder, gate_run_name
from surface_status.record import load_state, record, record_context
from surface_status.settings import Settings

SECONDS_PER_MINUTE = 60
TIMEOUT_MINUTES = 30  # for the whole run, every command included
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
class Step:
    """One command of the run, and how it ended."""

    command: str
    execution: Execution


@dataclass(frozen=True, slots=True)
class NotDeclared:
    """The approved plan names no gate command: nothing runs and the gate guards are lifted."""


@dataclass(frozen=True, slots=True)
class NotStarted:
    """The run was refused before it started, for a reason the journal already knows."""

    refusal: Refusal


@dataclass(frozen=True, slots=True)
class Ran:
    """A run that finished, and what the journal made of it."""

    run: int
    report: str  # `gates/run-NN.txt`, relative to the plan folder
    steps: tuple[Step, ...]  # the commands that ran, in order: the last one failed, or all passed
    seconds: float
    recorded: Accepted | Refusal

    @property
    def result(self) -> GateResult:
        return self.steps[-1].execution.result

    @property
    def exit_code(self) -> int | None:
        """The exit code of the last command that ran, None when it was killed at the timeout."""
        return self.steps[-1].execution.exit_code


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


def run_all(commands: tuple[str, ...], cwd: Path, timeout_seconds: float) -> tuple[Step, ...]:
    """Run the commands in order until one fails, all of them within `timeout_seconds`."""
    deadline = time.monotonic() + timeout_seconds
    steps: list[Step] = []
    for command in commands:
        left = deadline - time.monotonic()
        if left <= 0:
            execution = Execution(GateResult.TIMEOUT, None, 0.0, "")
        else:
            execution = execute(command, cwd, left)
        steps.append(Step(command, execution))
        if execution.result is not GateResult.PASS:
            break
    return tuple(steps)


def _exit_text(execution: Execution, timeout_seconds: float) -> str:
    code = execution.exit_code
    if code is None:
        return f"none (killed: the run reached its timeout of {timeout_seconds:g} seconds)"
    if code < 0:
        return f"{code} (killed by signal {-code})"
    return str(code)


def render_report(
    commands: tuple[str, ...], steps: tuple[Step, ...], seconds: float, timeout_seconds: float
) -> str:
    """Write the text of `gates/run-NN.txt`: the run, then each command in order."""
    result = steps[-1].execution.result
    lines = [
        f"result: {result.value}",
        f"duration: {seconds:.1f} seconds",
        f"timeout: {timeout_seconds:g} seconds for the whole run",
        f"commands: {len(commands)}, in order, stopping at the first that fails",
    ]
    for number, command in enumerate(commands, start=1):
        lines.extend(("", f"command {number}: {command}"))
        if number > len(steps):
            lines.append("not run: an earlier command failed")
            continue
        execution = steps[number - 1].execution
        lines.extend(
            (
                f"result: {execution.result.value}",
                f"exit code: {_exit_text(execution, timeout_seconds)}",
                f"duration: {execution.seconds:.1f} seconds",
                f"output (last {TAIL_LINES} lines at most):",
                "",
                execution.tail,
            )
        )
    return "\n".join(lines).rstrip("\n") + "\n"


# A path starts after a character that cannot end a name, and ends before one that cannot go on
# it: `/home/me` is found in `rootdir: /home/me/app` and `file:///home/me`, not in `/x/home/me`,
# `/home/me-2` or `/home/me.d`, while a full stop that ends a sentence is left after it.
_PATH_START = r"(?<![\w.-])"
_PATH_END = r"(?![\w-]|\.\w)"


def home_directory() -> Path | None:
    """Find the home directory of the user running the gates, None when the system names none."""
    try:
        return Path.home()
    except RuntimeError:
        return None


def neutral_paths(text: str, root: Path, home: Path | None) -> str:
    """Write the project root as `.` and the home directory as `~`, the longest path first.

    Each is matched as given and resolved, since a tool may print either. The file system root
    is never replaced: it would turn every absolute path into a relative one.
    """
    forms: dict[str, str] = {}
    for path, neutral in ((home, "~"), (root, ".")):
        if path is None:
            continue
        for form in (str(path), str(path.resolve())):
            if Path(form).is_absolute() and Path(form) != Path(form).parent:
                forms[form] = neutral
    if not forms:
        return text
    found = "|".join(re.escape(form) for form in sorted(forms, key=len, reverse=True))
    pattern = re.compile(f"{_PATH_START}(?:{found}){_PATH_END}")
    return pattern.sub(lambda match: forms[match[0]], text)


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
    """Run the gates of the approved plan and record the result; the timeout defaults to 30 min."""
    state = load_state(folder)
    commands = None if state is None else state.approved_gates
    if not commands:
        return NotDeclared()
    limit = TIMEOUT_MINUTES * SECONDS_PER_MINUTE if timeout_seconds is None else timeout_seconds
    number = folder.next_gate_run()
    # A failed run is the one that counts as a pass, so it is the one asked about: it is refused
    # from a state that takes no gate run and past the ceiling, where a green one would be too.
    asked = admit(
        state,
        GatesRun(run=number, result=GateResult.FAIL),
        record_context(folder, state, settings),
    )
    if isinstance(asked, Refusal):
        return NotStarted(asked)
    started = time.monotonic()
    steps = run_all(commands, root, limit)
    seconds = time.monotonic() - started
    name = gate_run_name(number)
    text = neutral_paths(render_report(commands, steps, seconds, limit), root, home_directory())
    _write_new(folder.path(name), text)
    result = steps[-1].execution.result
    recorded = record(folder, GatesRun(run=number, result=result), settings, now)
    return Ran(number, name, steps, seconds, recorded)
