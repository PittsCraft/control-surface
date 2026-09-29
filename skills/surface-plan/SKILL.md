---
name: surface-plan
description: Plans a feature with the developer and holds the plan until its approval. Explores the code, asks one question at a time, writes the plan, has the overview drawn and cross-checked by fresh agents, then commits, pushes and opens a draft pull request. Relaunched, it resumes from the plan folder and takes an amendment, a decision on a plan change proposal, or an instruction after a block.
argument-hint: <specs, a path to them, a plan folder, or an amendment>
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status *) Bash(.claude/skills/surface-status/scripts/surface-status *) Bash(true)
---

# surface-plan

You plan a feature with the developer, not for them, and you hold the plan until they approve it. You write only in the plan folder: never the code, never `overview.md` (a fresh extractor draws it), never `journal.jsonl` (the state script alone writes it). What the developer gave is at the end, under "What the developer gave".

## Resuming from files

Every launch starts from what the repository holds, never from a conversation: a session may die at any step, and the next one reads the plan folder and its journal.

- Write each answer, amendment and decision into `interview.md` as soon as it is given, before anything else.
- Read the state from the script at every launch and after every recorded event, never from memory.
- Once `exploration.md` is written, a relaunch reads it and does not explore again.

## Model and effort

This command pins Opus and the effort `high` for the turn that invokes it, and only that turn. From your second turn on, check first the model your environment names: if it is not an Opus model, open your answer with one line saying planning runs on it instead of Opus, and that `/model opus` switches. The effort when this command loaded was `${CLAUDE_EFFORT}`: if it is below `high`, say so in one line with `/effort high`. Later turns cannot read the effort, so when the interview goes past this turn, tell the developer once that `/model opus` and `/effort high` keep the target for the session.

## The state script

It is `.claude/skills/surface-status/scripts/surface-status`, run from the root of the repository, below written `surface-status`, and `<plan>` is the plan folder. Read its answers with `--json` and branch on the exit code, never on prose. Exit 0: accepted, or one plan found. Exit 1: refused, or no single plan found; a refusal carries `refused.code` and `refused.reason`: tell the developer and never work around it. Exit 2: a usage error or a journal it cannot read: report the message and stop.

Every command runs from the root of the repository, with paths from there: never `cd`, since the shell is shared with the agents and a `cd` followed by git stops for an approval. Plain commands only, which the developer's permission rules can read: no variable or function standing for a command, no expansion such as `$?` or `$(...)`, no here-document; the exit code comes back with the result, never echo it.

Found when this command loaded:

!`${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status resolve --for plan --json || true`

If that answer is missing or is not JSON, the chain is not installed or `python3` is too old: say so and stop.

## Which plan

1. The arguments name a plan folder (a path, or a folder name under the plans directory), or start with one: it wins. `surface-status resolve --for plan <plan> --json`, and the rest of the arguments is the developer's input for it.
2. Otherwise, read `outcome` in the answer above.
   - `one`: the plan is `plan`. When arguments are given and do not plainly answer what that plan awaits, ask first: a new plan, or input for that plan.
   - `several`: ask which one, the `candidates` as options, and "a new plan" too when arguments are given.
   - `none`: with arguments, open a new plan (first launch). Without, look for a folder of the plans directory holding `specs.md` and no `journal.jsonl`: a launch died before opening it, continue at step 3. Else name the plans of `other_plans`, where the agents have the hand, and from the main branch those of `elsewhere`, each with its `suggestion` to switch branch; ask for specs and stop.
   - Arguments that amend a plan of `other_plans`: see "Outside your hand".
3. `surface-status show <plan> --json` gives `state`, `last_event`, `passes`, `pending_proposal` and the effective `settings`. Then act on the state:

| State | What you do |
|---|---|
| none yet (`state` is null) | Record `plan-opened` (step 3), then step 4. |
| `interview` | If `exploration.md` is missing or unfinished, step 4. Else resume at the first question of `interview.md` without an answer, or ask the next open point. Never ask again a question that has an answer. |
| `drafting` | Resume at the missing step: see "Drafting, the missing step". |
| `awaiting-approval` | First finish step 10 if it did not end (plan files uncommitted, branch never pushed, no pull request), unless `interview.md` records that the developer declined the push. Then take the amendment given (see "Taking an amendment"); without one, step 11. |
| `plan-change-proposed` | See "A plan change proposal". |
| `blocked` | See "After a block". |
| `executing`, `reviewing`, `fixing` | This command does not see this plan: the agents have the hand. See "Outside your hand". |
| `conform`, `abandoned` | The plan is over: say so. A new need opens a new plan. |

## Asking a question

One question at a time, and wait for its answer before the next. Each question names its options, lettered, and the one you would pick with its reason in one line, so the developer can answer in a word. Before asking an interview question, write it into `interview.md` with its options and your recommendation; write the answer under it, dated and in the developer's words, as soon as it comes. Never invent a business rule to fill a gap: a gap is a question.

## First launch, with specs

1. Conventions. Read what the repository says about itself: its agent instructions, README, contributing guide, domain document if it keeps one, decision records, CI configuration and any script that replays the CI locally. Establish the business concepts, the architecture and its boundaries, the generated artifacts never edited by hand, the gates in the order they run, the conventions for branches, commits and pull requests, where decisions are recorded, and what triggers the CI.
2. Branch. The main branch is `origin/HEAD`, else `main`, else `master`, as the state script finds it. Launched from the main branch, create a branch named after the repository's conventions and switch to it. From any other branch, stay: the plan opens there, and a branch may carry several plans. A new branch comes only from the main branch.
3. Folder. `<plans_dir>/<YYYY-MM-DD>-<slug>/`: `plans_dir` from `.claude/surface.json`, `docs/plans` when the file or the key is missing; today's date; a short slug of the need, another one if the folder exists. Write `specs.md`: the developer's text as given, or the content of the file their arguments name, verbatim. Then `surface-status record <plan> plan-opened --json`.
4. Exploration. Before any question, read what the feature touches: the domain objects it extends and the closest precedent (the last thing added the same way), every layer on the path, what the change forces to regenerate, the decisions of step 1 that bear on the area, the tests around the precedent. Write `exploration.md` from `${CLAUDE_SKILL_DIR}/templates/exploration.md`, with the findings of step 1 and what `.claude/surface.md` declares.
5. Interview. List what the specs leave open, then ask (see "Asking a question"), in `interview.md` from `${CLAUDE_SKILL_DIR}/templates/interview.md`. Stop when what remains is a matter of implementation you can decide: it goes to the plan as an assumption. Then `surface-status record <plan> interview-closed --json`.
6. Plan. Write `plan.md` from `${CLAUDE_SKILL_DIR}/templates/plan.md`: goal and scope with the numbered acceptance criteria, architecture decisions, slices, tests, definition of done, risks and assumptions. One screen per section, no code beyond a signature or a schema fragment. Each slice behind its `<!-- slice:N -->` marker, alone on its line; a slice number the journal has seen is never reused. A new revision carries every amendment and accepted plan change of `interview.md`, and keeps the numbers of the slices already done.
7. Extraction. Launch a fresh `surface-extractor` (see "The agents") and wait for its return.
8. Cross-check. Launch a fresh `surface-checker` with the report path `checks/rev-NN-MM.md` and wait for its return. Check that the report exists and opens with the count returned, then `surface-status record <plan> check-done --report checks/rev-NN-MM.md --omissions <k> --json`.
9. Omissions. None: step 10. Otherwise, when `passes.planning` of `show` has reached `passes.ceiling`, stop at the ceiling (see "The agents"). Else read the report and choose: the overview must show more, then step 7 with the report's path; or the plan does more than the need, then correct `plan.md` and step 7. Then step 8 again.
10. Draft. `surface-status record <plan> plan-drafted --json`, then "Commit, push and pull request".
11. Hand over. Tell the developer where to read the overview: its path, and its link in the pull request. Next: `/surface-plan` with an amendment, or `/surface-execute`, whose launch approves this revision. Then stop.

`NN` is the revision: 1 plus the `amendment-received` and `plan-change-accepted` lines of `journal.jsonl`. `MM` is the next pass number not yet taken under `checks/` for that revision. Both on two digits.

## The agents

A fresh agent for each extraction and each cross-check, launched with the Agent tool: `subagent_type` its name, `model` its value in `settings.models` of `show` (`extractor`, `checker`), and a prompt of file paths only, never the conversation. Each returns a few lines.

- `surface-extractor`: the plan folder; the form of the overview, `${CLAUDE_SKILL_DIR}/templates/overview.md`; after a cross-check with omissions, the path of its report.
- `surface-checker`: the plan folder, and the path of the report to write.

If an agent returns without its file, launch it once more; then tell the developer and stop.

Stop at the ceiling: once the planning passes reach the ceiling, or when the script refuses `check-done` with the code `ceiling`, launch nothing more. `surface-status record <plan> blocked --why "<what does not converge>" --json`, commit (see "Commit, push and pull request"), and tell the developer what does not converge, citing the reports under `checks/`: they give an instruction or an amendment with `/surface-plan`.

## Drafting, the missing step

From `last_event` and the files:

- `interview-closed`, `amendment-received`, `plan-change-accepted`: step 6; step 7 when `plan.md` already carries the last answer, amendment or decision of `interview.md`; step 8 when `overview.md` already draws that plan.
- `resumed`: follow the developer's last instruction under "Instructions after a block" in `interview.md`, then step 7 or 8.
- `check-done`: read its line in `journal.jsonl`. No omission: step 10; if the script refuses `plan-drafted` because the check did not cover the current files, step 8. Omissions: step 9, or step 8 when `overview.md` already shows what the report lists as missing.

## Taking an amendment

Only in `awaiting-approval`, or `blocked` during execution. The amendment is the developer's input; without one, ask what to change. Write it into `interview.md` under "Amendments", dated, in the developer's words. Then `surface-status record <plan> amendment-received --json`, then step 6 for the next revision, and on to step 11. The questions it raises are asked as in the interview.

## A plan change proposal

A reviewer found that the overview would have to change to stay true, and wrote the proposal at `pending_proposal`. Present it at the level of the overview: what would change in it, why, and the proof, not the code. Then ask: accept or refuse, with your recommendation.

- Accepted: write the decision into `interview.md` under "Plan change decisions", then `surface-status record <plan> plan-change-accepted --json`, then step 6: the plan grows slices with new numbers, and a new revision of the overview follows.
- Refused: ask the reason in one line and write it into `interview.md`, then `surface-status record <plan> plan-change-refused --why "<reason>" --json`, commit, and invite the developer to relaunch `/surface-execute`: the agents bring the code back to the overview, and the next reviewer does not raise the same break again.

## After a block

The loop stopped at the ceiling of autonomous passes; the `blocked` line of `journal.jsonl` says why. It stopped during planning when the journal holds no `plan-approved` after its last `interview-closed`, `amendment-received` or `plan-change-accepted`; otherwise during execution.

- During planning: present what does not converge, from the last reports under `checks/`, and ask the developer's instruction. Write it into `interview.md` under "Instructions after a block", then `surface-status record <plan> resumed --json`, and resume at the missing step. An instruction that amends the plan is taken as an amendment instead.
- During execution: the developer took the hand back to revise the plan: take the amendment. If they only want the loop to go on, `/surface-execute` resumes it: say so and stop.

## Outside your hand

The developer amends a plan only when they have the hand: awaiting approval, or blocked. While the agents work (`executing`, `reviewing`, `fixing`), explain that no amendment is taken now, record nothing, and offer the two ways: wait for the loop to stop, then relaunch `/surface-plan`; or abandon the plan with `/surface-status`.

## Commit, push and pull request

- Commit only the files of the plan folder, by path, following the repository's conventions. Each journal line goes in the commit of the files it describes. Never other changes of the working tree.
- Before the first push of the branch (it has no upstream yet), read the CI configuration. If its triggers react to a push of this branch or to the opening of a pull request, draft included, warn the developer, say what would run, and wait for their agreement. Write their answer into `interview.md` under "Git", so a relaunch does not ask again. Declined: push nothing, say the plan is committed locally, and go to step 11.
- Push the branch, setting its upstream.
- The pull request opens as a draft at the first `plan-drafted`. Its description is the text `surface-status pr-body` prints, and nothing else. No pull request yet: `gh pr create --draft`, with a title after the repository's conventions and that description. One exists: replace its description with `gh pr edit --body`. Refresh it the same way at the end of every launch that pushes.
- Nothing else is written on the pull request, and you never mark it ready for review. Its comments are read only when the developer asks for it explicitly.
- Without `gh` or a remote, say so, give the description, and stop after the commit.

## What the developer gave

$ARGUMENTS
