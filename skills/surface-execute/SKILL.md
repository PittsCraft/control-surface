---
name: surface-execute
description: Approves a drafted plan, then hands its slices, reviews and fixes to fresh agents and runs the full gates, until the plan is conform or the loop hands back to the developer. Takes the plan folder as an optional argument.
argument-hint: "[plan]"
disable-model-invocation: true
model: sonnet
allowed-tools: Bash(${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status *) Bash(git add *) Bash(git commit *) Bash(git push *) Bash(gh pr edit *) Bash(gh pr ready *)
---

# surface-execute

You dispatch the execution of a plan. Launched on a plan awaiting approval, you approve it: the developer's launch is the approval. Then you hand each slice, each review and each fix to a fresh agent, run the full gates through the state script, and record each outcome, until the plan is conform or the loop hands back to the developer. You write neither code nor plan: agents write them, the state script writes the journal, you record through the script and commit.

## Ground rules

- The state lives in files: the plan folder and its `journal.jsonl`. Before every step, read it again: `surface-status show <plan> --json`, and the journal when a row below needs a fact from it. Never decide a step from memory of this conversation, nor from an agent's word when a file says it: an agent's return points at files, and the files decide.
- The state script is `${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status`, run from the root of the repository; below it is written `surface-status`, and `<plan>` is the plan folder. Only the script writes the journal. Exit code 0 is accepted, 1 refused with its reason, 2 a usage error. A refusal is never worked around: stop and report it.
- A fresh agent for every slice, every review, every fix and every suspected break: one Agent call with `subagent_type` set to the role, `surface-executor` or `surface-reviewer`, and `model` set to that role's model under `settings.models` of `show --json`. Its prompt gives the plan folder, file paths and the facts its mandate lists below, never a summary of this conversation. Never resume an agent that already returned.
- One agent at a time. Wait for its result before the next step, even when it arrives in a later turn, and start nothing meanwhile.
- You never edit a file. You commit through git, by pathspec, following the repository's commit conventions. A journal line goes in the same commit as the files it describes: the reports it cites, `plan.md` for a `plan-amended`. You push only when the loop stops.
- Your target model is Sonnet. If a later turn of this loop runs on another model, carry on, and say so in one line when the loop stops.

## Finding the plan

The developer's argument, empty when none: $ARGUMENTS

- With an argument: `surface-status resolve --for execute <plan> --json`. The plan the developer names wins, whatever its state.
- Without: `surface-status resolve --for execute --json`. Exit 0: the plan is its `plan`. Exit 1 with several `candidates`: list them with their state, ask the developer to relaunch `/surface-execute` naming one, and stop. Exit 1 with none: say what `other_plans` and `elsewhere` hold, a plan that belongs to `/surface-plan`, a plan on another branch with its `suggestion` to switch, and stop.

## Interrupted work

At launch, before the first row, run `git status` and read the journal:

- Journal lines not committed yet: `slice-done` or `fix-done` means the executor stopped between its record and its commit; make that commit, its work with the journal. A `plan-amended` with neither after it belongs to the step still under way: leave it, with the work, to the next executor. Any other line: commit the journal with the files its lines describe.
- A report under `reviews/` or `plan-changes/`, or a `conformity.md`, that no journal line cites is the return of a reviewer interrupted before its record: record it as "A review" or "A slice" says, instead of launching a new reviewer.
- Any other uncommitted work belongs to the interrupted step: the fresh agent of that step is told about it, rereads it, then continues or undoes it.

## The loop

Read the state, apply the first row that holds, read the state again, and so on until a row stops. The first two rows record an act of the developer: they apply only once, at launch.

| State found | What you do |
|---|---|
| `awaiting-approval`, at launch | Say in one line the plan and the revision you approve, the `rev` of the last `plan-drafted`. Then `surface-status record <plan> plan-approved` and commit the journal. |
| `blocked` during execution, at launch | `surface-status record <plan> resumed`, and commit the journal. |
| `plan-change-proposed` | Stop. Name the proposal, `pending_proposal` of `show --json`, and invite the developer to run `/surface-plan`, which presents it. |
| `conform`, `abandoned` | Stop: the plan is over. |
| `interview`, `drafting`, `blocked` during planning, or no event yet | Stop: this plan belongs to `/surface-plan`. |
| Ceiling reached, and work left to the agents | See "At the ceiling". |
| `executing` | See "A slice". |
| `reviewing`, the last event a clean review, nothing changed since | See "Conformity". |
| `reviewing`, no green gate run since the last change | See "Gates". |
| `reviewing`, gates green | See "A review". |
| `fixing` | See "A fix". |

How to read the rows:

- `blocked` during execution: the last `plan-approved` of the journal comes after every `amendment-received` and `plan-change-accepted`. Otherwise it is `blocked` during planning.
- Ceiling reached: `passes.execution` of `show --json` is at least `passes.ceiling`. Work is left to the agents in `executing`, in `fixing`, and in `reviewing` unless the conformity row holds: recording `conform` is the one step the ceiling lets through.
- A clean review: a `review-done` with no defect, no deviation and no break. Nothing changed since: no commit after the one that carries it, and no change in the working tree outside the plan folder.
- No green gate run since the last change: the journal holds no `gates-run` with the result `pass` after its last `plan-approved`, `slice-done` and `review-done`. When `settings.gate_command` is null, the project declares no gates, and they count as green.
- No progress: when an agent returns, the journal has not moved, and it reports neither a suspected break nor a refusal, stop and report. Never launch the same step twice in a row without progress.

## A slice

Launch a fresh `surface-executor`. Its mandate: the plan folder, and the slice to carry out, the first of `slices.remaining`. Add, when they hold:

- the developer's last act is a refusal of a plan change (the last of `plan-approved`, `plan-change-refused` and `resumed` in the journal is a `plan-change-refused`): its reason, and the proposal it refused;
- the last event is a `suspicion-dismissed` for this slice: the reviewer's note it cites;
- `git status` shows uncommitted work: it belongs to the interrupted step.

Its return:

- `slice N done`: back to the loop.
- `suspected break`, with its reason. Only a reviewer qualifies a break: launch a fresh `surface-reviewer` on that single question. Its mandate: the plan folder, the base commit (`base` of `surface-status commits <plan> --json`), and the mode, a break suspected during slice N, with the executor's reason. It reads the uncommitted work too.
  - `confirmed`, with the proposal: `surface-status record <plan> plan-change-proposed --proposal <path> --slice <n>`. Then one commit: the proposal, the unfinished work of the slice and the journal, so that nothing is left outside the repository. The proposal says the slice is unfinished.
  - `dismissed`, with the note: `surface-status record <plan> suspicion-dismissed --slice <n> --report <path>`. Commit the note and the journal, not the work: the next executor resumes the slice from it, with the note.
- Anything else, a refusal included: stop and report it.

## Gates

`surface-status gate <plan>` runs the project's full gates, writes their report under `gates/` and records `gates-run`. The run may last up to `settings.gate_timeout_minutes`: give the call the longest timeout the tool allows. If the tool moves the run to the background, check its output file at intervals until the run ends: never end the turn waiting for a notification.

- Exit 0, gates green: commit the run report and the journal.
- Exit 1 with a run report, gates failed or timed out: the state moves to `fixing` and the run counts as a pass. Commit the report and the journal.
- Exit 1 with a refusal, the ceiling for one: stop and report it.
- Exit 0 saying the project declares no gate command: nothing is recorded, go on.

## A review

Launch a fresh `surface-reviewer`. Its mandate: the plan folder, the base commit (`base` of `surface-status commits <plan> --json`), and the mode, a review. It reviews everything the branch changes against its merge base with the main branch, the developer's own commits included, and reads the latest gate run.

Its return names the report. Read the three counts in the report itself, then `surface-status record <plan> review-done --report <path> --defects <n> --deviations <n> --breaks <n>`, adding `--proposal <path>` on a break. Then one commit: the report, the proposal, `conformity.md` when the reviewer wrote it, and the journal.

## A fix

Launch a fresh `surface-executor` in fix mode. Its mandate: the plan folder, the fix mode, and everything that motivates the fix since the last `fix-done`:

- the report of the last `review-done`, its defects and deviations;
- the report under `gates/` of each failed `gates-run`, which the next fix starts from;
- the reason of a `plan-change-refused`, and the proposal it refused;
- the uncommitted work in the working tree, which belongs to the interrupted fix.

The fixer runs the full gates once at its end. Green, it records `fix-done` and commits; failed, it commits nothing and returns the run report. Both move the journal: back to the loop.

## Conformity

The last review found nothing and nothing changed since: the reviewer wrote `conformity.md`. `surface-status record <plan> conform --conformity conformity.md`, then commit the journal, with `conformity.md` if it is not committed yet. Stop.

## At the ceiling

The loop does not converge within its autonomous passes: the developer takes the hand back. Launch no fix.

1. `surface-status record <plan> blocked --why "<reason>"`, the reason naming on one line what does not converge. Commit the journal.
2. Stop, and say in the terminal: blocked, the developer takes the hand back; a summary of what does not converge, from the reports of the passes (review counts with their paths, failed gate runs, dismissed suspicions); and the two ways on: relaunch `/surface-execute` to resume where the loop stopped with a fresh count, or amend the plan with `/surface-plan`.

## When the loop stops

The loop stops on a row that says so, on a refusal of the script, on an agent's return the steps above do not expect, and on no progress. A refusal `overview-changed` means `overview.md` was modified after its approval: nothing goes on until the developer restores the approved content or abandons the plan with `/surface-status`.

At every stop, once a plan was found:

1. Say in the terminal why the loop stopped and who has the hand, with the paths worth reading.
2. Push the branch to its upstream, which `/surface-plan` set at the first draft. Without an upstream, push nothing and say so.
3. Refresh the pull request's description: the output of `surface-status pr-body`, given to `gh pr edit --body-file -` on its standard input. Without a pull request or without `gh`, say so. Nothing else is written on the pull request.
4. On `conform`, and only when `settings.mark_pr_ready` is true: `gh pr ready`. Otherwise the developer marks it ready, since that triggers the CI.
