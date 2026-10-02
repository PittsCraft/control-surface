# Architecture

This page describes the chain as it is now. Read it first. The few decisions whose history matters have a record in [docs/adr/](docs/adr/README.md), linked where they apply; everything else is said here, with its reason in one sentence. A pull request that changes the architecture updates this page.

## Purpose

control-surface is a chain of Claude Code skills and agents that a developer installs into their own project, the host. The developer approves the blueprint of a feature: it is their control surface, the level they steer from, below the product specs and above the code. Agents then build it, run the project's gates and review the work against that blueprint, pass after pass, until it conforms or the loop hands back. The developer reads the blueprint, neither the code nor the proof of conformity: a criterion the reviewer cannot prove is a finding that sends the loop round again, so conform leaves nothing to check, with one exception: the code of the critical zones the host declares, which the developer reads themselves, from the list of changed files the pull request description gives. Everything the chain knows lives in files of the host repository, so any session may die and the next one resumes.

## The parts

```text
developer --types--> commands: /surface-plan  /surface-execute  /surface-status
                        |    one fresh agent at a time, given file paths only
                        |---------------------> agents: extractor, checker, executor, reviewer
                        v                          v
             state script: surface-status  (record, show, resolve, gate, commits, pr-body, check)
                        |  sole writer                  |  reads only
                        v                               v
             plan folder: journal.jsonl + documents     git: branch, merge base, other branches

install.py --copies--> host .claude/skills/surface-*/ and .claude/agents/surface-*.md
host CI    --runs----> surface-status check --require conform
```

- **Commands** are three skills the developer types. `/surface-plan` explores, interviews, writes `plan.md` and its gates, has the blueprint drawn and cross-checked, then commits, pushes and opens a draft pull request. It then keeps the hand and takes amendments in the conversation, as it does after a block during planning, since a reply that approves nothing needs no new launch. `/surface-execute` approves the drafted revision by being launched, then dispatches slices, gate runs, reviews and fixes. It puts a plan change proposal and the ceiling to the developer in the conversation: a refusal or a resumption goes on in the session, while an accepted change or an amendment goes to `/surface-plan`, since this command cannot load it and never writes the plan. `/surface-status` reports, runs the conformity check, and abandons a plan on confirmation.
- **Agents** are four roles. The extractor draws `blueprint.md` from `plan.md`, as long as the feature needs, since the developer reads all of it: a section the plan does not change has no heading and one closing line names it, a diagram is drawn only when it shows what the prose does not, and a written section keeps its number, so that section 9 stays section 9 wherever it is named. The checker looks for what the plan does and the blueprint does not show, never for a short section or a diagram that is not there. The executor carries out a slice or a fix. The reviewer judges the branch against the approved blueprint, writes `conformity.md` when it finds nothing, with the changed files of the critical zones, judges a break an executor suspects, and corrects that list of files when the script refuses it.
- **The state script** derives the state, refuses illegal steps, runs the gates, and answers the skills and the host's CI.
- **A plan folder**, `docs/plans/<date>-<slug>/` by default, holds the specs, the exploration, the interview, the plan, the blueprint, the reports (`checks/`, `reviews/`, `plan-changes/`, `gates/`), `conformity.md` and `journal.jsonl`. It is the whole state of a plan.
- **The installer** copies the chain into the host, updates it, and checks it for drift.

## Codemap

- `skills/surface-plan/`: the planning command, and `templates/` for the exploration, the interview, the plan and the blueprint.
- `skills/surface-execute/SKILL.md`: the dispatch loop, a table of rows read top to bottom after every step.
- `skills/surface-status/`: the status command, and `scripts/surface-status`, a POSIX shell launcher that refuses a Python below 3.11, then runs the package `surface_status`:
  - `events.py` (the 20 events), `machine.py` (the 10 states, the transition table as data, `apply`), `guards.py` (`admit`, `fold`, the guards): the pure core, which opens no file.
  - `journal.py` and `strict_json.py`: the strict codec and the append-only writer.
  - `plan_folder.py`: paths, content hashes, the slice markers and gates block of `plan.md`, the critical-files block of `conformity.md`, report numbers.
  - `build.py` builds an event from the caller's judgments; `record.py` replays, admits, checks the disk and appends.
  - `gates.py`: the gate runner. `gitops.py`: git facts. `resolve.py`: the plans of a branch, the plan a command acts on, the commits of a plan.
  - `report.py` (list, `show`, `check`), `pr_body.py`, `settings.py`, and `cli.py` (arguments, exit codes, JSON).
- `agents/surface-*.md`: the four roles.
- `install.py`: install, update, `--check`, and the one-line form.
- `tests/`: one folder per part (`state`, `journal`, `cli`, `git`, `gates`, `install`, `prompts`), `ci/`, `e2e/`, and golden files in `fixtures/`.
- `scripts/gate.sh`: every gate. `scripts/check_commit_msg.py`: the commit message hook.

## Invariants

- Only the state script writes a journal, one appended line per accepted event, and a caller passes judgments only: the script derives dates, hashes, slices, gates and numbers ([ADR 0012](docs/adr/0012-script-computes-derived-fields.md)).
- State is never stored. It is the fold of the journal, and a replay reads no other file ([ADR 0011](docs/adr/0011-pure-fold-and-two-families-of-guards.md)).
- The approved blueprint is frozen: a change to it stops the loop until the developer restores it or abandons the plan.
- No agent edits, rewrites or deletes a report the script or another agent wrote (`gates/`, `reviews/`, `checks/`, `plan-changes/`, `conformity.md`): one that fails a gate stops the loop, since a report reworded by the step it judges proves nothing. One exception: a fresh reviewer corrects the list of critical files of `conformity.md` that the script refused, and nothing else in it.
- A gate result is a fact the script measures, never an agent's word: `gates-run` cannot be recorded by hand ([ADR 0034](docs/adr/0034-gates-named-by-the-plan-run-by-the-script.md)).
- A suspected break waits in the journal for a reviewer, and nothing carries its slice on before that ([ADR 0033](docs/adr/0033-a-suspected-break-kept-in-the-journal.md)).
- The runtime is Python 3.11 and the standard library only, and the state script has no network access ([ADR 0001](docs/adr/0001-python-311-standard-library.md)).
- The script never writes to git, and reads other branches from git objects, never by a checkout ([ADR 0016](docs/adr/0016-plans-of-a-branch-from-git-objects.md)).
- The installer writes only in its namespace, and creates no settings file ([ADR 0019](docs/adr/0019-ownership-by-namespace.md)).
- No prompt pins or checks the session's model or effort ([ADR 0031](docs/adr/0031-session-model-left-to-the-developer.md)), and the chain ships no permission rule ([ADR 0032](docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md)).
- Every agent is a leaf: no `Agent` tool, no `isolation`, no `permissionMode`. A role does its mandate itself, a slice's work must stay on the branch for the next step, and the host decides what runs unattended.
- Every command sets `disable-model-invocation: true`: launching `/surface-execute` is an approval, which only the developer gives, and no sentence of a conversation approves a revision.
- Each step goes to a fresh agent that reads files, never a conversation, one agent at a time.
- Prompts run every command from the repository root as a plain command: no `cd`, no `git -C`, no `find -exec`, no `$(...)`, since a permission rule matches plain command text only.
- The chain never marks a pull request ready: that triggers the host's CI, so the developer does it, when they want, once the plan is conform. `conformity.md` is the audit trail the `conform` event cites, never a required reading.
- No test asserts the prose of the README or of these documents ([ADR 0032](docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md)).
- No file holds an em dash, and no commit message carries an attribution.

## Crosscutting concerns

### Journal and state

A journal line is `v`, `at`, `event`, then the event's fields in declared order, in one canonical JSON form. A line that does not re-encode to the same text is refused, so a hand edit fails at replay with its line number. The writer appends one line and flushes it; a journal without a final newline, what a torn write leaves, is refused. Every command replays the journal. The pass counters live in the state and each act of the developer resets them. A pass is one time the loop sends work back to an agent: in planning a cross-check with omissions, which sends the blueprint or the plan back for rework, in execution a review's defects or deviations, a failed gate run or a dismissed suspicion. So a clean check, a clean review or a green run costs none, and in both loops the pass after the ceiling is still recorded, since it holds what does not converge, and hands back: one setting gives as many reworks in planning as fixes in execution. A content hash is the SHA-256 of the bytes with CRLF read as LF, so other line endings never read as an edit of a frozen blueprint.

### Guards

`admit` checks the transition table, then the guards, and returns an acceptance or a refusal with a code. Journal-only guards run at replay and at record. Record-time guards need the ceiling, the approved gates and the current blueprint hash, passed as plain values, and run at record only, so a changed setting never invalidates an old journal. Disk guards check that cited files sit inside the plan folder and that hashes and slices match the files; for a `conform`, they also take what git says the branch changed (see "Critical zones"). Skills branch on the refusal code, never on its prose.

### Gates

`/surface-plan` finds the commands that check the host (manifest, build files, CI, `AGENTS.md`, `CLAUDE.md`) and writes them in the `gates` block of `plan.md`; approval pins them. `surface-status gate` first asks the journal and runs nothing it would refuse, past the ceiling for instance. It runs the commands in order, each in its own process group, stops at the first failure, kills the group after 30 minutes for the whole run, writes `gates/run-NN.txt` and records `gates-run`. A failed run costs a pass ([ADR 0034](docs/adr/0034-gates-named-by-the-plan-run-by-the-script.md)). The report names the repository root `.` and the home directory `~`, since it is committed in the plan folder and the host's text checks read it. A run takes the number after the highest run of the journal and the highest report on disk, so a deleted report never frees its number and no report is ever overwritten.

### Plans of a branch

The plans of a branch are the plan folders it adds against its merge base with the main branch, so a plan kept on main after an earlier merge is never the branch's. The main branch is `origin/HEAD`, else `main`, `master`, `origin/main`, `origin/master`, with no setting. `resolve` designates the plan a command acts on, or hands the choice to the developer; it finds a plan for a command only in a state that command's skill takes, so a relaunch without an argument finds what the command would resume. `commits` assigns each commit to the plans whose journal it touches ([ADR 0016](docs/adr/0016-plans-of-a-branch-from-git-objects.md)). `pr-body` describes them in the pull request, refreshed whole at every stop: each plan's state and links, then, one line each and for information, the decisions agents took within the contract, read from the journal (a `plan-amended` with its reason, a `suspicion-dismissed` with the reason of the suspicion and its note), since the developer did not see them go by. Before them, for a conform plan, it lists the changed files of the critical zones, under a heading that says they are for the developer to read themselves.

### Critical zones

The developer reads the blueprint and not the code, except where a mistake would cost most: the code of the zones the host declares critical, which they read themselves. The zones stay declared in prose in the host's `AGENTS.md` or `CLAUDE.md`, and which files they cover is an agent's reading: a setting listing critical paths, which the script could match against the diff, would be one more thing to configure and a second place that declares the zones. Section 9 of the blueprint, always written, names each declared zone the plan touches, or says it touches none, and the cross-check counts a touched zone it does not name as an omission, so the developer learns at approval which code they will read. At conformity the reviewer lists the files the branch changed inside those zones in a `critical-files` fenced block of `conformity.md`, one path from the project root per line, at most one block, none when there is no such file. The script is the block's only reader. `conform` is refused (`critical-files`) when the block is malformed or lists a file the branch did not add, modify or delete against its merge base, since a wrong list would hide code to read or send the developer to code that did not change; outside a git work tree only the form is checked. A refused list is an agent's mechanical mistake, and the developer is never sent to `conformity.md` to repair it: `/surface-execute` launches a fresh reviewer, whose only mandate is to correct that block, then records `conform` again, up to `max_autonomous_passes` times, and hands back to the developer when the list is still refused after them. The one setting that bounds what the loop does on its own bounds this too, rather than a second number. The count is kept by the prompt, since a refused `conform` leaves no journal line for the script to count: these attempts raise no pass counter, and need no journal event, no new gate run and no new review. `pr-body` then shows the list of each conform plan, linked like the other files, a deleted file named as gone, and stops on a `conformity.md` broken after the record instead of saying there is nothing to read. Nothing is written into the frozen blueprint after its approval.

### Command line contract

Exit code 0 means accepted or passed, 1 refused or failed, 2 a wrong call or an unreadable journal. With `--json`, each answer is one object with `"v": 1`; a field is added without a new version, and renamed or removed only with `"v": 2`. The skills and the host's CI depend on both, and `tests/fixtures/cli/` pins the shapes.

### Install and drift

`install.py` is Python, not shell, so it shares the gates and the tests; it parses on old interpreters to say it needs 3.11 instead of failing on syntax. It owns `.claude/skills/surface-*/` and `.claude/agents/surface-*.md`, removes what the source dropped, and refuses to overwrite a file with uncommitted work unless `--force` ([ADR 0019](docs/adr/0019-ownership-by-namespace.md)). `--check` writes nothing and reports `missing`, `drift`, `orphan` and `uncommitted`. Piped from the public repository, it downloads the archive of `--ref` (`main` by default), unpacks it by hand, and installs as from a clone.

### Settings and language

The chain needs no configuration. `.claude/surface.json` is optional and the developer's: `plans_dir`, `max_autonomous_passes` (3) and `models`. An unknown key is refused with the closest known one, a removed key with what replaced it. The agents read the host's conventions and critical zones in `AGENTS.md` or `CLAUDE.md`. Plan documents are written in the repository's language, since they are committed next to its code and documentation: a language the host's agent instructions declare, else that of its documentation, else that of `specs.md`, found once by `/surface-plan` and written in `exploration.md`, where every agent reads it. The conversation stays in the developer's language, and their own words, in `specs.md` and `interview.md`, are quoted as given, then translated, so the evidence of what was said survives; what a script reads (markers, the gates and critical-files tags, the journal) never depends on either language.

### Permissions and models left to the developer

The loop stops at every command the developer's rules or mode do not allow, and the guide (`docs/guide.md`) leaves the choice of mode to the developer. A command's `allowed-tools` grant and a skill's model and effort hold for one turn only, and a session cannot read the rules in force. So the chain neither ships nor checks permission rules ([ADR 0032](docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md)), and pins only the agents' models, passed from `surface.json` on each Agent call, with `effort: high` on the three judgment roles ([ADR 0031](docs/adr/0031-session-model-left-to-the-developer.md)).

### Tests

Unit and hypothesis property tests cover each part of the script and the installer, with sockets blocked; the `ci` profile runs 500 examples. Golden journals replay to their expected states. Prompt tests hold the frontmatter, the contract the prompts carry (`tests/prompts/chain_contract.py`), host neutrality and privacy. The privacy check reads plan folders, where a path of the machine is a leak too, while the decision-link check skips them, since a plan names decisions still to come. `tests/ci/` proves the conformity check in a checkout shaped like a CI's, and the `conformity` job of `ci.yml` runs it again on a real runner. End to end tests run real sessions on a toy project, in a container, on demand only, since they are billed ([ADR 0025](docs/adr/0025-end-to-end-on-a-toy-project.md)).

### Toolchain

`scripts/gate.sh` is the one entry point and CI runs it, so CI only confirms a local run. It runs ruff with `select = ["ALL"]`, so new rules are not missed; mypy and pyright, both strict, since they disagree in useful places; the `claude` plugin validation when the CLI is present; then pytest on 3.11 with coverage and on the newest Python. Coverage is printed, never a threshold, which would get padded with empty tests. uv holds the toolchain in a committed lock. CI pins its actions by SHA, reads only, and skips drafts. A `commit-msg` hook refuses an em dash or an attribution.
