"""The command line of `surface-status` (ARCHITECTURE.md, Command line contract).

Exit codes: 0 accepted or check passed, 1 refused or check failed, 2 usage error or unreadable
journal. With `--json`, every answer on standard output is one JSON object carrying `"v": 1`, so a
skill or a CI job branches on the code and reads the fields, never the prose.
"""

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, TextIO

from surface_status import gates, gitops, pr_body, report, resolve
from surface_status.build import GATE_EVENT, PARAMS, Kind, Param, build_event
from surface_status.events import GateResult
from surface_status.guards import Accepted, InvalidJournalError, Refusal
from surface_status.journal import JournalError
from surface_status.plan_folder import PlanFolder, PlanFolderError
from surface_status.record import record, timestamp
from surface_status.report import UnreadableJournalError
from surface_status.settings import Settings, SettingsError, load_settings, settings_path

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2

PROG = "surface-status"


class UsageError(Exception):
    """Something the caller must fix, answered with exit code 2."""


def _line(text: str) -> str:
    stripped = text.strip()
    if not stripped or "\n" in stripped or "\r" in stripped:
        message = "expected one non-empty line of text"
        raise argparse.ArgumentTypeError(message)
    return stripped


def _whole(text: str, least: int) -> int:
    if not text.isascii() or not text.isdecimal() or int(text) < least:
        message = f"expected a whole number of at least {least}, got {text!r}"
        raise argparse.ArgumentTypeError(message)
    return int(text)


_TYPES: Mapping[Kind, Callable[[str], object]] = {
    Kind.LINE: _line,
    Kind.PATH: _line,
    Kind.COUNT: lambda text: _whole(text, 0),
    Kind.SLICE: lambda text: _whole(text, 1),
}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        text = f"{self.prog}: {message}"
        raise UsageError(text)


def _common(parser: argparse.ArgumentParser, *, top: bool) -> None:
    """Add `--json` and `--root`; on a subcommand they keep the value given before it."""
    parser.add_argument(
        "--json",
        action="store_true",
        default=False if top else argparse.SUPPRESS,
        help="answer in JSON",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None if top else argparse.SUPPRESS,
        help="the project root (default: the git work tree)",
    )


def _plan_argument(parser: argparse.ArgumentParser, *, optional: bool) -> None:
    parser.add_argument(
        "plan",
        nargs="?" if optional else None,
        help="the plan folder, by path or by name under the plans directory",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog=PROG, description="Where the plans of a project stand.")
    _common(parser, top=True)
    commands = parser.add_subparsers(dest="command", parser_class=_Parser)

    def add(name: str, summary: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=summary, description=summary)
        _common(sub, top=False)
        return sub

    _plan_argument(
        add("show", "state, next step, remaining slices, passes, settings"), optional=True
    )
    abandon = add("abandon", "record the abandonment of a plan")
    _plan_argument(abandon, optional=True)
    abandon.add_argument("--why", type=_line, required=True, help="the reason, on one line")
    check = add("check", "validate the journals, and with --require the conformity")
    check.add_argument("plans", nargs="*", help="plan folders (default: every plan)")
    check.add_argument(
        "--require",
        choices=[report.REQUIRE_CONFORM],
        help="every plan must be conform, or abandoned before its approval",
    )
    resolver = add("resolve", "name the plan a command must act on")
    resolver.add_argument(
        "--for", dest="target", choices=resolve.COMMANDS, required=True, help="the command asking"
    )
    _plan_argument(resolver, optional=True)
    commits = add("commits", "the commits of the branch that belong to a plan, and to none")
    _plan_argument(commits, optional=False)
    add("pr-body", "the description of the pull request, from the state")
    gate = add("gate", "run the gates of the approved plan and record the result")
    _plan_argument(gate, optional=False)
    recorder = add("record", "check the transition and its guards, then append the event")
    _plan_argument(recorder, optional=False)
    events = recorder.add_subparsers(dest="event", required=True, parser_class=_Parser)
    for name, params in PARAMS.items():
        sub = events.add_parser(name, help=f"record {name}")
        _common(sub, top=False)
        for param in params:
            _add_param(sub, param)
    reserved = events.add_parser(GATE_EVENT, help="not recorded by hand, see `gate`")
    _common(reserved, top=False)
    reserved.add_argument("--result", help=argparse.SUPPRESS)  # parsed, to be refused with a reason
    return parser


def _add_param(parser: argparse.ArgumentParser, param: Param) -> None:
    parser.add_argument(
        f"--{param.key}",
        type=_TYPES[param.kind],
        required=param.required,
        help=param.help,
        dest=param.key,
    )


class _Output:
    def __init__(self, stdout: TextIO, stderr: TextIO, *, as_json: bool) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.as_json = as_json

    def answer(self, payload: report.Payload, text: str) -> None:
        if self.as_json:
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        else:
            self.stdout.write(text)

    def failure(self, payload: report.Payload, text: str) -> None:
        """Report a failure: JSON stays on standard output, text goes to standard error."""
        if self.as_json:
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        else:
            self.stderr.write(text)

    def usage(self, message: str) -> int:
        payload = {"v": report.JSON_VERSION, "ok": False, "error": message}
        text = message if message.startswith(PROG) else f"{PROG}: {message}"
        self.failure(payload, text + "\n")
        return EXIT_USAGE


@dataclass(frozen=True, slots=True)
class _Run:
    """What one invocation works with."""

    out: _Output
    root: Path
    settings: Settings
    cwd: Path
    now: datetime


def _find_root(start: Path) -> Path:
    for folder in (start, *start.parents):
        if (folder / ".git").exists() or (folder / ".claude" / "surface.json").is_file():
            return folder
    return start


def _resolve_plan(run: _Run, argument: str | None) -> PlanFolder:
    if argument is None:
        return _the_plan_in_progress(run)
    plans_dir = run.settings.plans_dir
    for base in (run.cwd, run.root, run.root / plans_dir):
        candidate = base / argument
        if candidate.is_dir():
            return PlanFolder(candidate.resolve())
    message = f"no plan folder {argument!r} (looked from {run.cwd}, {run.root} and {plans_dir})"
    raise UsageError(message)


def _the_plan_in_progress(run: _Run) -> PlanFolder:
    """Pick the one plan of the branch that is not over; else the caller names it."""
    found = resolve.resolve(run.root, run.settings, None)
    chosen = found.chosen
    if chosen is not None:
        return chosen.folder
    where = found.branch or "the project"
    if found.matching:
        names = ", ".join(listed.name for listed in found.matching)
        message = f"several plans of {where} are in progress ({names}): name the plan"
    else:
        message = f"no plan of {where} is in progress: name the plan"
        if found.elsewhere:
            names = ", ".join(f"{item.plan} on {item.branch}" for item in found.elsewhere)
            message += f" (in progress on other branches: {names})"
    raise UsageError(message)


def _list(run: _Run) -> int:
    rows: list[report.Payload] = []
    unreadable = False
    for folder in resolve.branch_folders(run.root, run.settings):
        try:
            rows.append(report.plan_row(report.read_plan(folder)))
        except UnreadableJournalError as error:
            unreadable = True
            rows.append(report.error_row(folder.name, str(error)))
    payload = report.list_payload(rows)
    run.out.answer(payload, report.render_list(payload))
    return EXIT_USAGE if unreadable else EXIT_OK


def _show(run: _Run, folder: PlanFolder) -> int:
    payload = report.show_payload(report.read_plan(folder), run.settings)
    run.out.answer(payload, report.render_show(payload))
    return EXIT_OK


def _check(run: _Run, args: argparse.Namespace) -> int:
    if args.plans:
        folders = [_resolve_plan(run, name) for name in args.plans]
    else:
        folders = resolve.branch_folders(run.root, run.settings)
    results = [report.check_plan(folder, require=args.require) for folder in folders]
    payload = report.check_payload(results, require=args.require)
    text = report.render_check(payload)
    if payload["ok"]:
        run.out.answer(payload, text)
        return EXIT_OK
    run.out.failure(payload, text)
    return EXIT_USAGE if report.has_unreadable(results) else EXIT_REFUSED


def _resolve(run: _Run, args: argparse.Namespace) -> int:
    if args.plan is not None:
        payload = resolve.explicit_payload(args.target, _resolve_plan(run, args.plan))
    else:
        found = resolve.resolve(run.root, run.settings, args.target)
        payload = resolve.resolution_payload(args.target, found)
    text = resolve.render_resolution(payload)
    if payload["ok"]:
        run.out.answer(payload, text)
        return EXIT_OK
    run.out.failure(payload, text)
    return EXIT_REFUSED


def _commits(run: _Run, folder: PlanFolder) -> int:
    scope = resolve.branch_scope(run.root, run.settings)
    if scope is None:
        message = f"{run.root} is not in a git work tree: commits belong to a branch"
        raise UsageError(message)
    commits = gitops.commits_of_branch(run.root, scope.main)
    payload = resolve.commits_payload(folder.name, scope, commits, run.settings.plans_dir)
    run.out.answer(payload, resolve.render_commits(payload))
    return EXIT_OK


def _pr_body(run: _Run) -> int:
    payload = pr_body.describe(run.root, run.settings)
    if payload is None:
        message = "no plan on this branch: there is no description to write"
        run.out.failure({"v": report.JSON_VERSION, "ok": False, "error": message}, message + "\n")
        return EXIT_REFUSED
    run.out.answer(payload, payload["body"])
    return EXIT_OK


def _record(run: _Run, folder: PlanFolder, name: str, values: Mapping[str, object]) -> int:
    view = report.read_plan(folder)
    built = build_event(name, values, folder, view.events, view.state)
    result = built if isinstance(built, Refusal) else record(folder, built, run.settings, run.now)
    if isinstance(result, Accepted):
        payload: report.Payload = {
            "v": report.JSON_VERSION,
            "ok": True,
            "plan": folder.name,
            "event": name,
            "at": timestamp(run.now),
            "state": result.state.state.value,
        }
        run.out.answer(payload, f"recorded {name} for {folder.name}: state {payload['state']}\n")
        return EXIT_OK
    return _refused(run, folder.name, name, result)


def _refused(run: _Run, plan: str, event: str, refusal: Refusal) -> int:
    payload: report.Payload = {
        "v": report.JSON_VERSION,
        "ok": False,
        "plan": plan,
        "event": event,
        "refused": {"code": refusal.code.value, "reason": refusal.reason},
    }
    run.out.failure(payload, f"refused {event} ({refusal.code.value}): {refusal.reason}\n")
    return EXIT_REFUSED


def _gate(run: _Run, folder: PlanFolder) -> int:
    outcome = gates.run_gate(folder, run.root, run.settings, run.now)
    if isinstance(outcome, gates.NotDeclared):
        message = (
            "the approved plan names no gate command: nothing to run, the gate guards are lifted"
        )
        skipped: report.Payload = {
            "v": report.JSON_VERSION,
            "ok": True,
            "plan": folder.name,
            "ran": False,
            "reason": message,
        }
        run.out.answer(skipped, message + "\n")
        return EXIT_OK
    if isinstance(outcome, gates.NotStarted):
        return _refused(run, folder.name, GATE_EVENT, outcome.refusal)
    if isinstance(outcome.recorded, Refusal):
        return _refused(run, folder.name, GATE_EVENT, outcome.recorded)
    green = outcome.result is GateResult.PASS
    state = outcome.recorded.state.state.value
    payload: report.Payload = {
        "v": report.JSON_VERSION,
        "ok": green,
        "plan": folder.name,
        "ran": True,
        "run": outcome.run,
        "result": outcome.result.value,
        "exit_code": outcome.exit_code,
        "duration_seconds": round(outcome.seconds, 1),
        "commands": [
            {
                "command": step.command,
                "result": step.execution.result.value,
                "exit_code": step.execution.exit_code,
                "duration_seconds": round(step.execution.seconds, 1),
            }
            for step in outcome.steps
        ],
        "report": outcome.report,
        "at": timestamp(run.now),
        "state": state,
    }
    text = (
        f"gates {outcome.result.value} for {folder.name} (run {outcome.run}, "
        f"{outcome.seconds:.1f} s): {outcome.report}; state {state}\n"
    )
    if green:
        run.out.answer(payload, text)
        return EXIT_OK
    run.out.failure(payload, text)
    return EXIT_REFUSED


def _values(args: argparse.Namespace, params: Sequence[Param]) -> dict[str, object]:
    given = {param.key: getattr(args, param.key) for param in params}
    return {key: value for key, value in given.items() if value is not None}


def _record_by_hand(run: _Run, args: argparse.Namespace) -> int:
    if args.event == GATE_EVENT:
        message = (
            f"{GATE_EVENT} is recorded by `gate`, which runs the gates and keeps their "
            "exit code: an exit code is a fact, a hand written result is not"
        )
        raise UsageError(message)
    folder = _resolve_plan(run, args.plan)
    return _record(run, folder, args.event, _values(args, PARAMS[args.event]))


def _dispatch(run: _Run, args: argparse.Namespace) -> int:  # noqa: PLR0911 (one arm per command)
    match args.command:
        case None:
            return _list(run)
        case "show":
            return _show(run, _resolve_plan(run, args.plan))
        case "check":
            return _check(run, args)
        case "resolve":
            return _resolve(run, args)
        case "commits":
            return _commits(run, _resolve_plan(run, args.plan))
        case "pr-body":
            return _pr_body(run)
        case "gate":
            return _gate(run, _resolve_plan(run, args.plan))
        case "abandon":
            return _record(run, _resolve_plan(run, args.plan), "abandoned", {"why": args.why})
        case _:
            return _record_by_hand(run, args)


def main(
    argv: Sequence[str] | None = None,
    *,
    now: Callable[[], datetime] | None = None,
    cwd: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one command and return its exit code. The keywords let tests fix the world."""
    wants_json = "--json" in (sys.argv[1:] if argv is None else argv)
    out = _Output(
        sys.stdout if stdout is None else stdout,
        sys.stderr if stderr is None else stderr,
        as_json=wants_json,
    )
    where = Path.cwd() if cwd is None else cwd
    try:
        try:
            args = build_parser().parse_args(argv)
        except SystemExit as leaving:  # --help
            return leaving.code if isinstance(leaving.code, int) else EXIT_OK
        root = (args.root if args.root is not None else _find_root(where)).resolve()
        settings = load_settings(settings_path(root))
        moment = datetime.now(UTC) if now is None else now()
        return _dispatch(_Run(out, root, settings, where, moment), args)
    except (
        UsageError,
        SettingsError,
        UnreadableJournalError,
        JournalError,
        InvalidJournalError,
        PlanFolderError,
        gitops.GitError,
    ) as error:
        return out.usage(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
