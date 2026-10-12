# Architecture

This page says what the chain is now: its parts, where their code is, what they never do and how they work together. Read it first. A reason is given in a clause, and the few decisions whose history matters have a record in [docs/adr/](docs/adr/README.md), linked where they apply. What a prompt, a template or a guide says stays there, and this page names the file. `AGENTS.md` says what belongs here and when a pull request changes it.

## Purpose

Control Surface is a chain of Claude Code skills and agents that a developer installs into their own project, the host. The developer approves the blueprint of a feature: it is their control surface, the level they steer from, below the product specs and above the code.

Agents then build the feature, run the project's gates and review the work against that blueprint, pass after pass, until it conforms or the loop hands back. The developer reads the blueprint, neither the code nor the proof of conformity: a criterion the reviewer cannot prove is a finding that sends the loop round again. One exception: the code of the critical zones the host declares, which the developer reads themselves, from the list of changed files the pull request description gives.

Everything the chain knows lives in files of the host repository, so any session may die and the next one resumes.

## The parts

```text
developer --types--> commands: /surface-plan  /surface-execute  /surface-status
                        |    one fresh agent at a time, given file paths only
                        |---------------------> agents: Plan (built in), extractor, checker, executor, reviewer
                        v                          v
             state script: surface-status  (record, show, resolve, gate, commits, pr-body, check)
                        |  sole writer                  |  reads only
                        v                               v
             plan folder: journal.jsonl + documents     git: branch, merge base, other branches

install.py --copies--> host .claude/skills/surface-*/ and .claude/agents/surface-*.md
```

- **Commands** are three skills the developer types, each a `skills/surface-*/SKILL.md`.
  - `/surface-plan` explores, interviews, has the plan drafted and writes it with its gates, has the blueprint drawn and cross-checked, then commits, pushes and opens a draft pull request. It then stays in the conversation and takes amendments there, as it does after a block during planning, since a reply that approves nothing needs no new launch.
  - `/surface-execute` approves the drafted revision by being launched, then dispatches slices, gate runs, reviews and fixes. It puts a plan change proposal and the ceiling to the developer in the conversation. A refusal or a resumption goes on in the session; an accepted change or an amendment goes to `/surface-plan`, since this command cannot load it and never writes the plan.
  - `/surface-status` reports, runs the conformity check, and abandons a plan on confirmation.
- **Agents** are four roles of the chain, each an `agents/surface-*.md`, and one agent built into Claude Code.
  - The `Plan` agent, built in, drafts the plan in the form it chooses. The chain ships no definition for it and holds the plan only to the minimum it reads: the numbered acceptance criteria, the slices behind their markers, each enough for an agent that starts fresh, and the `gates` block ([ADR 0035](docs/adr/0035-plan-drafted-by-the-built-in-plan-agent.md)).
  - That agent has no write tool and cannot ask the developer anything. It returns the plan and `/surface-plan` writes `plan.md`. A rule it has to settle on its own is marked in the plan as an assumption, and the blueprint shows it as one that approving the page confirms: a question sent back would cost the developer a turn.
  - The extractor draws `blueprint.md` from `plan.md`: a fixed frame, the idea, the acceptance criteria and the scope first, the sensitive zones last, around a body cut for the feature. Its prompt and `skills/surface-plan/templates/blueprint.md` hold the form of the page.
  - The checker looks for what the plan does and the blueprint does not show, never for a cut, a short section or a diagram that is not there.
  - The executor carries out a slice or a fix.
  - The reviewer judges the branch against the approved blueprint, and a break an executor suspects. When it finds nothing it writes `conformity.md`, with the changed files of the critical zones, and it corrects that list when the script refuses it.
- **The state script** derives the state, refuses illegal steps, runs the gates, and answers the skills.
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
- `tests/`: one folder per part (`state`, `journal`, `cli`, `git`, `gates`, `install`, `prompts`, `evals`), `ci/`, `e2e/`, `gh/` for the stand-in `gh` of the end to end image, and golden files in `fixtures/`.
- `evals/`: the evaluations of the chain on real sessions. `host/`, a synthetic project the chain is installed in; `cases/`, one need per shape, each with a brief, acceptance tests the agents never see and a reference implementation; `judge/`, the rubric, the method of the count and the spoiled documents that check the judge; `surface_evals/`, the harness; `reports/`, the campaigns kept; `run.py`, its command line.
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
- Prompts run every command from the repository root, with paths from there, since the dispatcher and its agents share one shell. They say nothing else of how an agent writes a command, nor of the tool it changes a file with: the agent judges, and what stops for an approval is the permission mode's call ([ADR 0032](docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md)).
- The chain acts on nothing of the host's CI: it reads its configuration for the commands that check the project and their order, reads no trigger, asks nothing before a push, and gives the host no job to run, since each would bind the chain to what every host does its own way ([ADR 0037](docs/adr/0037-the-host-ci-left-to-the-host.md)). `check --require conformant` is the developer's command before merging, which a CI can call.
- The chain never marks a pull request ready: what the host runs then is the developer's to start, so the developer does it, when they want, once the plan is conformant. `conformity.md` is the audit trail the `conformant` event cites, never a required reading.
- No test asserts the prose of the README or of these documents: one may read their form, where a pointer leads or the size of a paragraph, never a sentence ([ADR 0032](docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md)).
- No file holds an em dash, and no commit message carries an attribution.

## Crosscutting concerns

### Journal and state

A journal line is `v`, `at`, `event`, then the event's fields in declared order, in one canonical JSON form. A line that does not re-encode to the same text is refused, so a hand edit fails at replay with its line number. The writer appends one line and flushes it; a journal without a final newline, what a torn write leaves, is refused. Every command replays the journal.

The pass counters live in the state, and each act of the developer resets them. A pass is one time the loop sends work back to an agent: in planning a cross-check with omissions, which sends the blueprint or the plan back for rework, in execution a review's defects or deviations, a failed gate run or a dismissed suspicion. So a clean check, a clean review or a green run costs none.

In both loops the pass after the ceiling is still recorded, since it holds what does not converge, and hands back: one setting gives as many reworks in planning as fixes in execution.

A content hash is the SHA-256 of the bytes with CRLF read as LF, so other line endings never read as an edit of a frozen blueprint.

### Guards

`admit` checks the transition table, then the guards, and returns an acceptance or a refusal with a code. Skills branch on the refusal code, never on its prose. The guards split by what they need:

- Journal-only guards run at replay and at record.
- Record-time guards need the ceiling, the approved gates and the current blueprint hash, passed as plain values. They run at record only, so a changed setting never invalidates an old journal.
- Disk guards check that cited files sit inside the plan folder and that hashes and slices match the files. For a `conformant`, they also take what git says the branch changed (see "Critical zones").

### Gates

`/surface-plan` finds the commands that check the host (manifest, build files, CI, `AGENTS.md`, `CLAUDE.md`) and holds the `gates` block of `plan.md` to them, whatever the agent that drafted the plan wrote there; approval pins them.

`surface-status gate` first asks the journal and runs nothing it would refuse, past the ceiling for instance. It runs the commands in order, each in its own process group, stops at the first failure, kills the group after 30 minutes for the whole run, writes `gates/run-NN.txt` and records `gates-run`. A failed run costs a pass ([ADR 0034](docs/adr/0034-gates-named-by-the-plan-run-by-the-script.md)).

The report names the repository root `.` and the home directory `~`, since it is committed in the plan folder and the host's text checks read it. A run takes the number after the highest run of the journal and the highest report on disk, so a deleted report never frees its number and no report is ever overwritten.

### Plans of a branch

The plans of a branch are the plan folders it adds against its merge base with the main branch, so a plan kept on main after an earlier merge is never the branch's. The main branch is `origin/HEAD`, else `main`, `master`, `origin/main`, `origin/master`, with no setting. Three subcommands read them:

- `resolve` designates the plan a command acts on, or hands the choice to the developer. It finds a plan for a command only in a state that command's skill takes, so a relaunch without an argument finds what the command would resume.
- `commits` assigns each commit to the plans whose journal it touches ([ADR 0016](docs/adr/0016-plans-of-a-branch-from-git-objects.md)).
- `pr-body` describes them in the pull request, refreshed whole at every stop: each plan's state and links, for a conformant plan the changed files of the critical zones, under a heading that says they are for the developer to read themselves, then the decisions agents took within the contract.

Those decisions are one line each, for information, read from the journal: a `plan-amended` with its reason, a `suspicion-dismissed` with the reason of the suspicion and its note. The developer did not see them go by.

### Critical zones

The developer reads the blueprint and not the code, except where a mistake would cost most: the code of the zones the host declares critical, which they read themselves. A zone goes from the host's declaration to the developer's reading in the steps below.

**Declared in prose.** The zones are declared in the host's `AGENTS.md` or `CLAUDE.md`, and which files they cover is an agent's reading. A setting listing critical paths, which the script could match against the diff, would be one more thing to configure and a second place that declares the zones.

**Touched by file.** A zone is touched as soon as the plan changes a file that holds its code: a file the host places in the zone, by its name, its folder or a pattern, or one whose code defines or computes what the zone protects. The extractor, the checker and the reviewer hold that definition in the same words, in their prompts, with what does not count: a file that only uses that code, tests it or describes it ([ADR 0038](docs/adr/0038-a-critical-zone-touched-by-file.md)).

**Announced at approval.** The closing section of the blueprint, the sensitive zones, opens on one sentence of fixed form: none, or each zone touched with the files of it the plan changes. The page then says how far the change goes, into what the zone protects or only into something else the file holds. So the developer learns at approval which code they will read, and the cross-check and the evaluations read the zones in that sentence. The cross-check counts a touched zone the page does not name as an omission.

**What the page binds.** A zone the page says is not touched is held as the contract: a branch or an amendment that changes a file of it makes the page false, a break like any other, and the developer decides. The files the page names for a touched zone are neither a criterion nor a promise on the layout of the code: the list at conformity is the reference.

**Listed at conformity.** The reviewer lists the files the branch changed inside the zones, whatever the blueprint named, in a `critical-files` fenced block of `conformity.md`: one path from the project root per line, at most one block, none when there is no such file. The script is the block's only reader.

**Checked by the script.** `conformant` is refused with the code `critical-files` when the block is malformed or lists a file the branch did not add, modify or delete against its merge base, since a wrong list would hide code to read or send the developer to code that did not change. Outside a git work tree only the form is checked.

**A refused list corrected by an agent.** It is an agent's mechanical mistake, and the developer is never sent to `conformity.md` to repair it. `/surface-execute` launches a fresh reviewer whose only mandate is to correct that block, then records `conformant` again, up to `max_autonomous_passes` times, and hands back when the list is still refused. The prompt keeps that count, since a refused `conformant` leaves no journal line: these attempts raise no pass counter, and need no new gate run and no new review.

**Shown to the developer.** `pr-body` shows the list of each conformant plan, a deleted file named as gone, and stops on a `conformity.md` broken after the record instead of saying there is nothing to read. `/surface-execute` hands back at conformity in one line that names those files, read from `pr-body --json`. Nothing is written into the frozen blueprint after its approval.

### Command line contract

Exit code 0 means accepted or passed, 1 refused or failed, 2 a wrong call or an unreadable journal. With `--json`, each answer is one object with `"v": 1`; a field is added without a new version, and renamed or removed only with `"v": 2`. The skills depend on both, as does a host that calls the check from its CI, and `tests/fixtures/cli/` pins the shapes.

### Install and drift

`install.py` is Python, not shell, so it shares the gates and the tests; it parses on old interpreters to say it needs 3.11 instead of failing on syntax. Piped from the public repository, it downloads the archive of `--ref` (`main` by default), unpacks it by hand, and installs as from a clone.

It owns `.claude/skills/surface-*/` and `.claude/agents/surface-*.md`, removes what the source dropped, and refuses to overwrite a file with uncommitted work unless `--force` ([ADR 0019](docs/adr/0019-ownership-by-namespace.md)). `--check` writes nothing and reports `missing`, `drift`, `orphan` and `uncommitted`.

### Settings and language

The chain needs no configuration. `.claude/surface.json` is optional and the developer's: `plans_dir`, `max_autonomous_passes` (3) and `models`. An unknown key is refused with the closest known one, a removed key with what replaced it. The agents read the host's conventions and critical zones in `AGENTS.md` or `CLAUDE.md`.

Plan documents are written in the repository's language, since they are committed next to its code and documentation: a language the host's agent instructions declare, else that of its documentation, else that of `specs.md`. `/surface-plan` finds it once and writes it in `exploration.md`, where every agent reads it.

The conversation stays in the developer's language and in the words the README and the guide teach them: the commands keep the chain's insides, the names of the agents and the paths of the reports, out of what they tell the developer.

The developer's own words, in `specs.md` and `interview.md`, are quoted as given, then translated, so the evidence of what was said survives. What a script reads (markers, the gates and critical-files tags, the journal) never depends on either language.

### Permissions and models left to the developer

The loop stops at every command the developer's rules or mode do not allow, and the guide (`docs/guide.md`) leaves the choice of mode to the developer. A command's `allowed-tools` grant and a skill's model and effort hold for one turn only, and a session cannot read the rules in force. So the chain neither ships nor checks permission rules ([ADR 0032](docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md)).

It pins only the agents' models, passed from `surface.json` on each Agent call, with `effort: high` on the three judgment roles ([ADR 0031](docs/adr/0031-session-model-left-to-the-developer.md)). The `Plan` agent has no definition to carry a default model or an effort: its model is the `planner` role, passed like the others, and it runs at the session's effort.

The attribution Claude Code adds to a commit is the host's setting too: no prompt asks for one or forbids one, as none says anything else of how a commit is written, and the installer creates no settings file, so the guide names the setting that turns it off.

### Tests

Unit and hypothesis property tests cover each part of the script and the installer, with sockets blocked; the `ci` profile runs 500 examples. Golden journals replay to their expected states. `tests/ci/` proves the conformity check in a checkout shaped like a CI's, and the `conformity` job of `ci.yml` runs it again on a real runner.

Prompt tests hold the frontmatter, the contract the prompts carry (`tests/prompts/chain_contract.py`), host neutrality and privacy. The privacy check reads plan folders, where a path of the machine is a leak too, while the decision-link check skips them, since a plan names decisions still to come. A form check bounds each paragraph of this page and the page itself, in bytes, so that a pull request cuts or moves before it adds.

End to end tests run real sessions on a toy project, in a container, on demand only, since they are billed ([ADR 0025](docs/adr/0025-end-to-end-on-a-toy-project.md)). The developer's answers are written in the test, one session per answer, and a path a kill would have to hit between two commands of one step starts from a prepared state that holds what a death there leaves. `tests/e2e/README.md` is their guide.

Their image reaches no GitHub. A stand-in, `tests/e2e/toy/gh_stand_in.py`, first on its `PATH`, answers the pull request calls of the prompts, refuses the others and keeps a record of every call, which the scenarios and the evaluations read. `tests/gh/` holds it without a session. It belongs to the test image only: nothing of it is installed in a host.

### Evaluations

The tests say that the chain works, not that it is worth using. The evaluations of `evals/` answer that after a change of the prompts, on real sessions and with no human in them, in the container of the end to end tests, on demand and never in CI ([ADR 0036](docs/adr/0036-evaluations-on-real-sessions.md)). `evals/README.md` is their guide.

A run plays the developer's side on a synthetic host. It types the need of a case, has a model answer each question from a written brief, then read the blueprint and send back what contradicts the brief, and launches `/surface-execute`. A campaign that measures a change of planning alone stops its runs at the hand over. Three things measure a run:

- A script measures what a script can, from the journal, the plan folder, the streams, the delivered code and what the stand-in `gh` kept: the outcome, the passes, acceptance tests kept from the agents, the critical zones, the form of the blueprint and the state of the pull request. On the toy, it tells whether a fault put there on purpose is found by the cross-check and classified by the review.
- A model judges the rest against a written rubric, the blueprint, the interview, the messages, each judgement with the passage it rests on.
- In a call of its own, that judge counts what the developer would skip on the blueprint: the facts said more than once in prose and the details of implementation that are not theirs to decide.

The judge is itself checked: a document spoiled in a known way must score below its original, and the padded blueprint must count more than the lean one.

A measure is kept as its spread over the runs, and the report says what lies outside the spread of the campaign before: there is no threshold, since what to hold is decided once the measures have been observed. A ledger stops a campaign before a ceiling, in USD at list price or in points of the subscription's weekly gauge.

### Toolchain

`scripts/gate.sh` is the one entry point and CI runs it, so CI only confirms a local run. It runs ruff with `select = ["ALL"]`, so new rules are not missed; mypy and pyright, both strict, since they disagree in useful places; the `claude` plugin validation when the CLI is present; then pytest on 3.11 with coverage and on the newest Python.

Coverage is printed, never a threshold, which would get padded with empty tests. uv holds the toolchain in a committed lock. CI pins its actions by SHA, reads only, and skips drafts. A `commit-msg` hook refuses an em dash or an attribution.
