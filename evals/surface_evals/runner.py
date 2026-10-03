"""One run of a case: the chain from the need to the delivered code, with nobody in the loop.

The run plays the developer's side of the README. It types the need after `/surface-plan`, has a
model answer each question from the brief of the case, then read the blueprint handed over and
correct what contradicts the brief, as an amendment. It gives the amendment of the case when it
has one, replies with a sentence that agrees, which must approve nothing, then launches
`/surface-execute`, whose launch approves. It stops when the plan is conformant or the
loop hands back, runs the acceptance tests the agents never saw, and writes `run.json`: what was
said at each stop, and what the files held then. Nothing is judged here: `measure` and `judge`
read the folder a run leaves.
"""

import json
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import cast

import toy

from surface_evals import CLONE
from surface_evals.budget import Ledger
from surface_evals.corpus import Acceptance, Case, copy_host, run_acceptance
from surface_evals.developer import NOTHING, answer, read_blueprint
from surface_evals.sessions import SessionLog, run_chain

RECORD = "run.json"
GATE = "python3 -m unittest discover -s tests -q"  # the gate the host states in its AGENTS.md
AGREEMENT = "Looks fine to me, go ahead."
EXECUTE = "/surface-execute"
MAX_TURNS = 14  # what the developer says to one planning conversation, at most
MAX_CORRECTIONS = 2  # the blueprints the developer sends back before they approve
MAX_LAUNCHES = 2  # `/surface-execute` relaunched once when a session ends with work left
AWAITING = "awaiting-approval"
AGENTS_TURN = frozenset({"executing", "reviewing", "fixing"})
OVER = frozenset({"conformant", "abandoned"})
HANDED_BACK = frozenset({"blocked", "plan-change-proposed"})


@dataclass(frozen=True, slots=True)
class Stop:
    """One thing the developer said, and where the session it went to stopped."""

    kind: str  # need, answer, correction, amendment, agreement, approval, relaunch
    said: str
    log: str  # the stream of the session, from the folder of the run
    state: str | None  # the state of the plan once the session ended
    final: str  # the final message of the session
    ended: bool  # False when the session was killed at the timeout


def build_project(dest: Path) -> Path:
    """Make `dest/lending`: the host on its main branch, pushed, with the chain installed."""
    project = dest / "lending"
    remote = dest / "origin.git"
    project.mkdir(parents=True)
    toy.git(dest, "init", "--quiet", "--bare", "--initial-branch=main", str(remote))
    toy.git(project, "init", "--quiet", "--initial-branch=main")
    for key, value in (
        ("user.name", "Eval Developer"),
        ("user.email", "developer@example.com"),
        ("commit.gpgsign", "false"),
        ("core.editor", "true"),
    ):
        toy.git(project, "config", key, value)
    copy_host(project)
    toy.write(project, {".gitignore": "__pycache__/\n"})
    toy.git(project, "add", ".")
    toy.git(project, "commit", "--quiet", "-m", "lending: lend the books of a library")
    subprocess.run(
        [sys.executable, str(CLONE / "install.py"), str(project)],
        cwd=project,
        capture_output=True,
        check=True,
    )
    toy.git(project, "add", ".claude")
    toy.git(project, "commit", "--quiet", "-m", "chain: install the control surface")
    toy.git(project, "remote", "add", "origin", str(remote))
    toy.git(project, "push", "--quiet", "--set-upstream", "origin", "main")
    toy.git(project, "remote", "set-head", "origin", "main")
    return project


def plan_of(project: Path) -> str | None:
    """Name the plan folder of a project, from its root: a run opens one plan."""
    journals = sorted(project.glob("docs/plans/*/journal.jsonl"))
    return journals[-1].parent.relative_to(project).as_posix() if journals else None


def state_of(project: Path) -> str | None:
    """Give the state the script derives for the plan of a project, None before it opens."""
    plan = plan_of(project)
    if plan is None:
        return None
    try:
        state = toy.show(project, plan)["state"]
    except (subprocess.CalledProcessError, ValueError):
        return "unreadable"
    return None if state is None else str(state)


def events_of(project: Path) -> list[dict[str, object]]:
    """Read the journal of the plan of a project, line by line."""
    plan = plan_of(project)
    if plan is None:
        return []
    lines: list[dict[str, object]] = []
    for raw in (project / plan / "journal.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            lines.append(cast("dict[str, object]", json.loads(raw)))
        except ValueError:
            continue  # a line being written while a session runs
    return lines


def count(project: Path, event: str) -> int:
    return sum(1 for line in events_of(project) if line.get("event") == event)


def gate_passes(project: Path) -> bool:
    done = subprocess.run(
        shlex.split(GATE), cwd=project, capture_output=True, check=False, timeout=600
    )
    return done.returncode == 0


def pr_body(project: Path) -> str:
    """Give the pull request description the state script writes for the branch."""
    done = subprocess.run(
        [str(project / toy.STATE_SCRIPT), "pr-body"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout if done.returncode == 0 else ""


@dataclass(slots=True)
class Run:
    case: Case
    root: Path
    ledger: Ledger
    developer_model: str
    project: Path = field(init=False)
    stops: list[Stop] = field(default_factory=list[Stop])
    blueprints: list[str] = field(default_factory=list[str])
    approved_by_sentence: bool | None = None
    outcome: str = "planning-stuck"
    acceptance: Acceptance | None = None
    gate: bool | None = None

    def __post_init__(self) -> None:
        self.project = build_project(self.root / "work")

    def _log(self, kind: str) -> Path:
        return self.root / "logs" / f"{len(self.stops) + 1:02d}-{kind}.jsonl"

    def _say(self, kind: str, said: str, resume: str | None) -> SessionLog:
        log = self._log(kind)
        session = run_chain(self.project, said, log, resume=resume)
        self.ledger.note(session)
        self.stops.append(
            Stop(
                kind=kind,
                said=said,
                log=log.relative_to(self.root).as_posix(),
                state=state_of(self.project),
                final=session.final,
                ended=session.ended,
            )
        )
        self.save()
        return session

    def _converse(
        self, kind: str, said: str, resume: str | None, handed_over: Callable[[], bool]
    ) -> str | None:
        """Say something to the planning session, then answer it until it hands a revision over.

        Returns the session to resume, or None when the conversation did not get there.
        """
        for _ in range(MAX_TURNS):
            if self.ledger.exhausted() is not None:
                self.outcome = "budget"
                return None
            session = self._say(kind, said, resume)
            resume = session.session_id or resume
            if handed_over():
                return resume
            state = self.stops[-1].state
            if not session.ended or resume is None or state in AGENTS_TURN | OVER:
                break
            reply = answer(
                self.case,
                session.final,
                self.root / "logs" / f"{len(self.stops):02d}-developer.jsonl",
                model=self.developer_model,
            )
            self.ledger.note(reply)
            kind, said = "answer", reply.final or "Nothing to add."
        return None

    def _keep_blueprint(self) -> None:
        plan = plan_of(self.project)
        if plan is None:
            return
        name = f"blueprint-rev-{len(self.blueprints) + 1:02d}.md"
        shutil.copyfile(self.project / plan / "blueprint.md", self.root / name)
        self.blueprints.append(name)

    def _drafted(self, revisions: int) -> Callable[[], bool]:
        def handed_over() -> bool:
            return (
                state_of(self.project) == AWAITING
                and count(self.project, "plan-drafted") >= revisions
            )

        return handed_over

    def _correction(self) -> str | None:
        """Have the developer read the blueprint handed over; None when they change nothing."""
        plan = plan_of(self.project)
        if plan is None or self.ledger.exhausted() is not None:
            return None
        drawn = (self.project / plan / "blueprint.md").read_text(encoding="utf-8")
        log = self.root / "logs" / f"{len(self.stops):02d}-developer-reads.jsonl"
        reply = read_blueprint(self.case, drawn, log, model=self.developer_model)
        self.ledger.note(reply)
        said = reply.final.strip()
        return None if not said or said.startswith(NOTHING.rstrip(".")) else said

    def _amend(self, kind: str, said: str, session: str) -> bool:
        """Give an amendment to the planning session, and keep the blueprint it hands over."""
        revision = len(self.blueprints) + 1
        if self._converse(kind, said, session, self._drafted(revision)) is None:
            return False
        self._keep_blueprint()
        return True

    def plan(self) -> bool:
        """Plan with the developer of the case until the revision they would approve awaits it."""
        need = f"/surface-plan {self.case.need}"
        session = self._converse("need", need, None, self._drafted(1))
        if session is None:
            return False
        self._keep_blueprint()
        for _ in range(MAX_CORRECTIONS):
            correction = self._correction()
            if correction is None:
                break
            if not self._amend("correction", correction, session):
                return False
        if self.case.amendment is not None and not self._amend(
            "amendment", self.case.amendment, session
        ):
            return False
        # A sentence that agrees approves nothing: only the launch of `/surface-execute` does.
        self._say("agreement", AGREEMENT, session)
        self.approved_by_sentence = count(self.project, "plan-approved") > 0
        return True

    def execute(self) -> None:
        """Launch the loop, which the launch approves, and once more if a session ends early."""
        for launch in range(MAX_LAUNCHES):
            if self.ledger.exhausted() is not None:
                self.outcome = "budget"
                return
            self._say("approval" if launch == 0 else "relaunch", EXECUTE, None)
            if self.stops[-1].state not in AGENTS_TURN:
                break
        state = self.stops[-1].state
        if state == "conformant":
            self.outcome = "conformant"
        elif state in HANDED_BACK:
            self.outcome = "handed-back"
        else:
            self.outcome = "execution-stuck"

    def close(self) -> None:
        """Run what the agents never saw, and keep what the branch says of itself."""
        self.acceptance = run_acceptance(self.case, self.project)
        self.gate = gate_passes(self.project)
        (self.root / "pr-body.md").write_text(pr_body(self.project), encoding="utf-8")
        self.save()

    def save(self) -> None:
        record: dict[str, object] = {
            "v": 1,
            "case": self.case.name,
            "project": self.project.relative_to(self.root).as_posix(),
            "plan": plan_of(self.project),
            "outcome": self.outcome,
            "approved_by_sentence": self.approved_by_sentence,
            "stops": [asdict(stop) for stop in self.stops],
            "blueprints": self.blueprints,
            "acceptance": None if self.acceptance is None else asdict(self.acceptance),
            "gate": self.gate,
        }
        (self.root / RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
