---
name: surface-execute
description: Approves a drafted plan, then hands its slices, reviews and fixes to fresh agents and runs the full gates, until the plan is conformant or the loop hands back to the developer. A plan change proposal or the ceiling is put to the developer in the conversation. Takes the plan folder as an optional argument.
argument-hint: "[plan]"
disable-model-invocation: true
allowed-tools: Bash(.claude/skills/surface-status/scripts/surface-status *) Bash(git add *) Bash(git commit *) Bash(git push *) Bash(gh pr edit *)
---

# surface-execute

You dispatch the execution of a plan. Launched on a plan awaiting approval, you approve it: the developer's launch is the approval. Then you hand each slice, each review and each fix to a fresh agent, run the full gates through the state script, and record each outcome, until the plan is conformant or the loop hands back to the developer. You write neither code nor plan: agents write them, the state script writes the journal, you record through the script and commit. When the loop hands back, you stay in the conversation wherever the developer's reply approves nothing new: a plan change proposal, the ceiling. A revision is approved only by the launch of this command, never by a sentence of the conversation, and after a dead session, relaunching it is the way to resume.

## Ground rules

- The state lives in files: the plan folder and its `journal.jsonl`. Before every step, read it again: `surface-status show <plan> --json`, and the journal when a row below needs a fact from it. Never decide a step from memory of this conversation, nor from an agent's word when a file says it: an agent's return points at files, and the files decide.
- The state script is `.claude/skills/surface-status/scripts/surface-status`, run from the root of the repository; below it is written `surface-status`, and `<plan>` is the plan folder. Only the script writes the journal. Exit code 0 is accepted, 1 refused with its reason, 2 a usage error. A refusal is never worked around: stop and report it.
- Every command runs from the root of the repository, with paths from there: never `cd`, since the shell is shared with the agents and a `cd` followed by git stops for an approval, nor `git -C`, which the permission rules do not read as the git command it runs.
- A fresh agent for every slice, every review, every fix, every suspected break and every refused list of critical files: one Agent call with `subagent_type` set to the role, `surface-executor` or `surface-reviewer`, and `model` set to that role's model under `settings.models` of `show --json`. Its prompt gives the plan folder, file paths and the facts its mandate lists below, never a summary of this conversation. Never resume an agent that already returned.
- One agent at a time. Ask for the foreground, `run_in_background` false, when the Agent tool offers it: the loop then stays in the turn the developer launched, with the grants of this command. Wait for the result before the next step, even when it arrives in a later turn, and start nothing meanwhile.
- You edit one file only: `interview.md` of the plan folder, where you write the developer's decisions on a plan change proposal, quoted in their words, then translated when theirs is not the documents' language. Never code, never `plan.md`, never `blueprint.md`. You commit through git, by pathspec, following the repository's commit conventions. A journal line goes in the same commit as the files it describes: the reports it cites, `plan.md` for a `plan-amended`, `interview.md` for a decision of the developer. You push only when the loop stops or hands back to the developer.
- You speak to the developer in the language they write in: what you say in the terminal is not repository content. What you write in the plan folder is in the documents' language, the language `exploration.md` names in its repository rules.

## Finding the plan

The developer's argument, empty when none: $ARGUMENTS

- With an argument: `surface-status resolve --for execute <plan> --json`. The plan the developer names wins, whatever its state.
- Without: `surface-status resolve --for execute --json`. Exit 0: the plan is its `plan`. Exit 1 with several `candidates`: list them with their state, ask the developer to relaunch `/surface-execute` naming one, and stop. Exit 1 with none: say what `other_plans` and `elsewhere` hold, a plan that belongs to `/surface-plan`, a plan on another branch with its `suggestion` to switch, and stop.

## Interrupted work

At launch, before the first row, run `git status` and read the journal:

- Journal lines not committed yet: `slice-done` or `fix-done` means the executor stopped between its record and its commit; make that commit, its work with the journal. A `plan-amended` with neither after it belongs to the step still under way: leave it, with the work, to the next executor. A `break-suspected` that nothing judged after it waits for its reviewer: leave it, with the work, and the loop launches the reviewer on it. A `plan-change-proposed` after a `break-suspected`: make the commit "A suspected break" describes, the unfinished work of the slice with it. Any other line: commit the journal with the files its lines describe.
- A report under `reviews/` or `plan-changes/`, or a `conformity.md`, that no journal line cites is the return of a reviewer interrupted before its record: record it as "A review" or "A suspected break" says, instead of launching a new reviewer.
- A decision of the developer in `interview.md` that no journal line records yet: "A plan change proposal" takes it.
- Any other uncommitted work belongs to the interrupted step: the fresh agent of that step is told about it, rereads it, then continues or undoes it.

## The loop

Read the state, apply the first row that holds, read the state again, and so on until a row stops. The two rows marked "at launch" record an act of the developer: they apply only once, at launch.

| State found | What you do |
|---|---|
| `alarms` of `show --json` not empty | Stop, and name each alarm. `blueprint-changed`: see "When the loop stops". |
| `awaiting-approval`, at launch | Say in one line the plan and the revision you approve, the `rev` of the last `plan-drafted`, and the gates it names, `gates` of `show --json`. Then `surface-status record <plan> plan-approved` and commit the journal. |
| `blocked` during execution, at launch | `surface-status record <plan> resumed`, and commit the journal. |
| `plan-change-proposed` | See "A plan change proposal". |
| `conformant`, `abandoned` | Stop: the plan is over. |
| `interview`, `drafting`, `blocked` during planning, or no event yet | Stop: this plan belongs to `/surface-plan`. |
| Ceiling reached, and work left to the agents | See "At the ceiling". |
| `executing`, a break suspected | See "A suspected break". |
| `executing` | See "A slice". |
| `reviewing`, the last event a clean review, nothing changed since | See "Conformity". |
| `reviewing`, no green gate run since the last change | See "Gates". |
| `reviewing`, gates green | See "A review". |
| `fixing` | See "A fix". |

How to read the rows:

- `blocked` during execution: the last `plan-approved` of the journal comes after every `amendment-received` and `plan-change-accepted`. Otherwise it is `blocked` during planning.
- A break suspected: `pending_suspicion` of `show --json` is not null. The executor recorded it, with its reason, before it returned, and no reviewer has judged it yet.
- Ceiling reached: `passes.execution` of `show --json` is more than `passes.ceiling`. A pass is one time the loop sends work back to an agent, for a review's defects or deviations, a failed gate run, a fixer's own included, or a dismissed suspicion; a clean review or a green run costs none. So the loop sends work back `passes.ceiling` times, and the pass after them hands back. Work is left to the agents in `executing`, in `fixing`, and in `reviewing` unless the conformity row holds: recording `conformant` is the one step the ceiling lets through.
- A clean review: a `review-done` with no defect, no deviation and no break. Nothing changed since: no commit after the one that carries it, and no change in the working tree outside the plan folder.
- No green gate run since the last change: the journal holds no `gates-run` with the result `pass` after its last `plan-approved`, `slice-done` and `review-done`. When `gates` of `show --json` is empty or null, the approved plan names no gates, and they count as green.
- No progress: when an agent returns, the journal has not moved, and it reports no refusal, stop and report. Never launch the same step twice in a row without progress. The reviewers "Conformity" sends to correct a refused list are the exception: they move no line, the record that follows them does, and their own bound is there.

## A slice

Launch a fresh `surface-executor`. Its mandate: the plan folder, and the slice to carry out, the first of `slices.remaining`. Add, when they hold:

- the developer's last act is a refusal of a plan change (the last of `plan-approved`, `plan-change-refused` and `resumed` in the journal is a `plan-change-refused`): its reason, and the proposal it refused;
- the last event is a `suspicion-dismissed` for this slice: the reviewer's note it cites;
- `git status` shows uncommitted work: it belongs to the interrupted step.

Its return:

- `slice N done`: back to the loop.
- `suspected break`: the executor recorded `break-suspected` with its reason and left its work uncommitted. Back to the loop, which finds it in `pending_suspicion`.
- Anything else, a refusal included: stop and report it.

## A suspected break

The executor's reason is in the journal, not in this conversation: a relaunch finds it just as this turn does. Only a reviewer qualifies a break: launch a fresh `surface-reviewer` on that single question. Its mandate: the plan folder, the base commit (`base` of `surface-status commits <plan> --json`), and the mode, a break suspected during slice N, with the executor's reason: `slice` and `why` of `pending_suspicion`. It reads the uncommitted work too.

- `confirmed`, with the proposal: `surface-status record <plan> plan-change-proposed --proposal <path> --slice <n>`. Then one commit: the proposal, the unfinished work of the slice and the journal, so that nothing is left outside the repository. The proposal says the slice is unfinished.
- `dismissed`, with the note: `surface-status record <plan> suspicion-dismissed --slice <n> --report <path>`. Commit the note and the journal, not the work: the next executor resumes the slice from it, with the note.
- Anything else, a refusal included: stop and report it.

## A plan change proposal

A reviewer found that the blueprint would have to change to stay true, and wrote the proposal at `pending_proposal` of `show --json`. The developer decides, and you stay in the conversation while they do.

1. When `interview.md` already holds the decision on this proposal, under "Plan change decisions", a relaunch after a session died: it is the reply of step 3, and nothing is asked again.
2. Otherwise, first do the steps of "When the loop stops", so the pull request shows whose turn it is. Then present the proposal yourself, at the level of the blueprint: what would change in it, why, and the proof, not the code. Ask: accept or decline, with your recommendation and its reason in one line.
3. The reply:
   - Declined: ask the reason in one line. Write the decision and the reason into `interview.md` under "Plan change decisions", quoted in the developer's words and translated, then `surface-status record <plan> plan-change-refused --why "<reason>"`, and commit `interview.md` with the journal. Back to the loop, in this session: the agents bring the code back to the blueprint, and the next reviewer does not raise the same break again.
   - Accepted: write the decision into `interview.md` under "Plan change decisions", then `surface-status record <plan> plan-change-accepted`, and commit `interview.md` with the journal. The plan is back in drafting, which belongs to `/surface-plan`: stop as "When the loop stops" says, and tell the developer to run `/surface-plan`, which draws the next revision and may ask its questions first. You draw no revision: you cannot load `/surface-plan`, and you never write the plan. The new revision is approved by a new launch of `/surface-execute`.
   - A question is answered from the files, and nothing is recorded. In doubt, ask whether the reply is a decision.

## Gates

`surface-status gate <plan>` runs the project's full gates, the commands the approved plan names, in order, writes their report under `gates/` and records `gates-run`. The run may last up to 30 minutes: give the call the longest timeout the tool allows. If the tool moves the run to the background, check its output file at intervals until the run ends: never end the turn waiting for a notification.

- Exit 0, gates green: commit the run report and the journal.
- Exit 1 with a run report, gates failed or timed out: the state moves to `fixing` and the run counts as a pass. Commit the report and the journal.
- Exit 1 with a refusal, the ceiling for one: stop and report it.
- Exit 0 with `ran` false, the approved plan names no gate command: nothing is recorded, go on.

## A review

Launch a fresh `surface-reviewer`. Its mandate: the plan folder, the base commit (`base` of `surface-status commits <plan> --json`), and the mode, a review. It reviews everything the branch changes against its merge base with the main branch, the developer's own commits included, and reads the latest gate run.

Its return names the report. Read the three counts in the report itself, then `surface-status record <plan> review-done --report <path> --defects <n> --deviations <n> --breaks <n>`, adding `--proposal <path>` on a break. Then one commit: the report, the proposal, `conformity.md` when the reviewer wrote it, and the journal.

## A fix

Launch a fresh `surface-executor` in fix mode. Its mandate: the plan folder, the fix mode, and everything that motivates the fix since the last `fix-done`:

- the report of the last `review-done`, its defects and deviations;
- the report under `gates/` of each failed `gates-run`, which the next fix starts from;
- the reason of a `plan-change-refused`, and the proposal it refused;
- the uncommitted work in the working tree, which belongs to the interrupted fix.

The fixer runs the full gates once at its end. Green, it records `fix-done` and commits; failed, it commits nothing and returns the run report. Both move the journal: back to the loop. The return `a report fails a gate` is a stop, even when the run moved the journal: no agent may edit a report of the script or of another agent, so another fix would fail the same way. Stop and report it.

## Conformity

The last review found nothing and nothing changed since: the reviewer wrote `conformity.md`. `surface-status record <plan> conformant --conformity conformity.md`, then commit the journal, with `conformity.md` when its content is not committed yet. Stop, as "When the loop stops" says, its push and its refresh first, then hand back in one line: the plan is conformant, and the developer marks the pull request ready when they want, which triggers their CI. When the refresh reached no pull request, for want of one, of `gh` or of a remote, that line names the step that fits instead: the developer opens the pull request, if none is open yet, with the description `surface-status pr-body` prints, the script given by its full path since they run it themselves. Nobody marks ready, or refreshes, a pull request that does not exist. Conformant means the reviewer proved every acceptance criterion, since one it cannot prove is a finding: `conformity.md` keeps that proof, and nothing asks the developer to read it. Say the one exception in one sentence: a conformant plan leaves nothing to check, except the code of the critical zones the project declares, whose changed files the pull request description lists, when there are any, for the developer to read themselves.

Refused with the code `critical-files`: the list of those files, which the reviewer left in `conformity.md` for the script, is malformed or names a file the branch did not change. The developer is not asked to repair an agent's list, and only a reviewer edits a reviewer's report: launch a fresh `surface-reviewer`. Its mandate: the plan folder, the base commit (`base` of `surface-status commits <plan> --json`), and the mode, a refused list of critical files, with the refusal's reason. It corrects that list and nothing else, and records nothing: when it returns, record `conformant` again, as above. Refused again: a fresh reviewer again, with the new reason, up to `passes.ceiling` of `show --json` reviewers in all, since the one setting that bounds what the loop does on its own bounds this too. Keep that count yourself: a refused `conformant` leaves no line in the journal, and these attempts do not raise `passes.execution`. Still refused after them: stop and report the reason to the developer.

## At the ceiling

The loop does not converge within its autonomous passes: it is the developer's turn again. Launch no fix.

1. `surface-status record <plan> blocked --why "<reason>"`, the reason naming on one line what does not converge. Commit the journal.
2. Do the steps of "When the loop stops", and say in the terminal: blocked, it is the developer's turn again; a summary of what does not converge, from the reports of the passes (review counts with their paths, failed gate runs, dismissed suspicions), and a suspected break still waiting for its reviewer, with its reason.
3. Stay in the conversation and ask: resume, or amend the plan, with your recommendation and its reason in one line.
   - Resume: `surface-status record <plan> resumed`, commit the journal, and back to the loop in this session, with a fresh count. A suspected break still waiting goes to its reviewer.
   - Amend: tell the developer to run `/surface-plan <amendment>`, which takes it and draws the next revision. Record nothing, and stop.
   - A question is answered from the files, and nothing is recorded.

A relaunch of `/surface-execute` on a plan blocked during execution resumes it too: the row "`blocked` during execution, at launch".

## When the loop stops

The loop stops on a row that says so, on a refusal of the script, on an agent's return the steps above do not expect, and on no progress. An alarm or a refusal `blueprint-changed` means `blueprint.md` was modified after its approval: nothing goes on until the developer restores the approved content or abandons the plan with `/surface-status`.

At every stop, once a plan was found:

1. Say in the terminal why the loop stopped and whose turn it is, with the paths worth reading.
2. Push the branch to its upstream, which `/surface-plan` set at the first draft. Without an upstream, push nothing and say so.
3. Refresh the pull request's description: the output of `surface-status pr-body` (it takes no argument, since it describes every plan of the branch), given to `gh pr edit --body-file -` on its standard input. Without a pull request or without `gh`, say so in one line. Nothing else is written on the pull request.
4. Never mark the pull request ready, since that triggers the CI: on `conformant`, the developer does, when they want, or opens it first when the refresh reached none.
