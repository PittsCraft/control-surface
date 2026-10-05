---
name: surface-plan
description: Plans a feature with the developer and holds the plan until its approval. Explores the code, asks one question at a time, has the plan drafted, the blueprint drawn and cross-checked by fresh agents, then commits, pushes and opens a draft pull request. It stays in the conversation and takes amendments there until the developer approves with /surface-execute. Relaunched, it resumes from the plan folder and takes an amendment, a decision on a plan change proposal, or an instruction after a block.
argument-hint: <specs, a path to them, a plan folder, or an amendment>
disable-model-invocation: true
allowed-tools: Bash(${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status *) Bash(.claude/skills/surface-status/scripts/surface-status *) Bash(true)
---

# surface-plan

You plan a feature with the developer, not for them, and you hold the plan until they approve it. You write only in the plan folder: never the code, never `blueprint.md` (a fresh extractor draws it), never `journal.jsonl` (the state script alone writes it). The plan is drafted by a fresh `Plan` agent, and you write it as returned. What the developer gave is at the end, under "What the developer gave".

## Resuming from files

Every launch starts from what the repository holds, never from a conversation: a session may die at any step, and the next one reads the plan folder and its journal.

- Write each answer, amendment and decision into `interview.md` as soon as it is given, before anything else.
- Read the state from the script at every launch and after every recorded event, never from memory.
- Once `exploration.md` is written, a relaunch reads it and does not explore again.
- Staying in the conversation changes none of this: a reply is written before it is acted on, and the state read again from the script. A revision is approved only by the launch of `/surface-execute`, never by a sentence of the conversation. After a dead session, relaunching `/surface-plan` is the way to resume.

## The state script

It is `.claude/skills/surface-status/scripts/surface-status`, run from the root of the repository, below written `surface-status`, and `<plan>` is the plan folder. Read its answers with `--json` and branch on the exit code, never on prose. Exit 0: accepted, or one plan found. Exit 1: refused, or no single plan found; a refusal carries `refused.code` and `refused.reason`: tell the developer and never work around it. Exit 2: a usage error or a journal it cannot read: report the message and stop.

Every command runs from the root of the repository, with paths from there: never `cd`, since the shell is shared with the agents and a `cd` followed by git stops for an approval, nor `git -C`, which the permission rules do not read as the git command it runs.

Found when this command loaded:

!`${CLAUDE_PROJECT_DIR}/.claude/skills/surface-status/scripts/surface-status resolve --for plan --json || true`

If that answer is missing or is not JSON, the chain is not installed or `python3` is too old: say so and stop.

## Which plan

1. The arguments name a plan folder (a path, or a folder name under the plans directory), or start with one: it wins. `surface-status resolve --for plan <plan> --json`, and the rest of the arguments is the developer's input for it.
2. Otherwise, read `outcome` in the answer above.
   - `one`: the plan is `plan`. When arguments are given and do not plainly answer what that plan awaits, ask first: a new plan, or input for that plan.
   - `several`: ask which one, the `candidates` as options, and "a new plan" too when arguments are given.
   - `none`: with arguments, open a new plan (first launch). Without, look for a folder of the plans directory holding `specs.md` and no `journal.jsonl`: a launch died before opening it, continue at step 3. Else name the plans of `other_plans`, where it is the agents' turn, and from the main branch those of `elsewhere`, each with its `suggestion` to switch branch; ask for specs and stop.
   - Arguments that amend a plan of `other_plans`: see "Not your turn".
3. `surface-status show <plan> --json` gives `state`, `last_event`, `passes`, `pending_proposal` and the effective `settings`. Then act on the state:

| State | What you do |
|---|---|
| none yet (`state` is null) | Record `plan-opened` (step 3), then step 4. |
| `interview` | If `exploration.md` is missing or unfinished, step 4. Else resume at the first question of `interview.md` without an answer, or ask the next open point. Never ask again a question that has an answer. |
| `drafting` | Resume at the missing step: see "Drafting, the missing step". |
| `awaiting-approval` | First finish step 10 if it did not end (plan files uncommitted, branch never pushed, no pull request), unless `interview.md` records that the developer declined the push. Then take the amendment given (see "Taking an amendment"); without one, step 11. |
| `plan-change-proposed` | See "A plan change proposal". |
| `blocked` | See "After a block". |
| `executing`, `reviewing`, `fixing` | This command does not see this plan: it is the agents' turn. See "Not your turn". |
| `conformant`, `abandoned` | The plan is over: say so. A new need opens a new plan. |

## Asking a question

One question at a time, and wait for its answer before the next. Each question names its options, lettered, and the one you would pick with its reason in one line, so the developer can answer in a word. Before asking an interview question, write it into `interview.md` with its options and your recommendation; write the answer under it, dated, in the developer's words then translated (see "Languages"), as soon as it comes. Never invent a business rule to fill a gap: a gap is a question.

## Languages

The conversation is the developer's, the plan folder is the repository's.

- Speak to the developer in the language they write in: questions, options, hand-overs and summaries in the terminal are not repository content.
- Every document of the plan folder is written in the documents' language, found at step 1 and written once in `exploration.md`, in its repository rules: every agent reads it there. The markers, the `gates` tag and the journal stay as they are, whatever the language.
- The developer's own words stay as given: `specs.md`, and each answer, amendment, decision and instruction written into `interview.md`, is quoted in their words, then, when their language differs from the documents', followed by its translation into the documents' language. Everything you write yourself is in the documents' language only. The agents work from the translation, and the original is the reference when the two disagree.

## First launch, with specs

1. Conventions. Read what the repository says about itself: its agent instructions, README, contributing guide, domain document if it keeps one, decision records, CI configuration and any script that replays the CI locally. Establish the business concepts, the architecture and its boundaries, the generated artifacts never edited by hand, the gates in the order they run, the conventions for branches, commits and pull requests, where decisions are recorded, and what triggers the CI.
   - The documents' language (see "Languages"), in this order: the first that answers wins. A language the agent instructions (`AGENTS.md`, `CLAUDE.md`) declare for what the repository holds. Otherwise the language of the repository's own documentation, its README and the plans it already holds. Otherwise the language the specs are written in.
2. Branch. The main branch is `origin/HEAD`, else `main`, else `master`, as the state script finds it. Launched from the main branch, create a branch named after the repository's practice, as below, and switch to it. From any other branch, stay: the plan opens there, and a branch may carry several plans. A new branch comes only from the main branch.
   - Find the practice in this order, and stop at the first that answers. A convention written in what step 1 read (agent instructions, contributing guide) wins. Otherwise the head branches of past pull requests, which outlive the branches deleted after merge: the developer's own first, `gh pr list --state all --author @me --limit 50 --json headRefName`, then the team's, `gh pr list --state all --limit 50 --json headRefName,author`, leaving out the branches of bots. Without `gh`, or when it finds no pull request, the remote branches, `git branch -r`, and the subjects of merge commits, `git log --merges --format=%s -n 50`, which name the branch they merged.
   - Follow the dominant prefix. With typed prefixes (`feat/`, `fix/`, `chore/`...), take the one that matches the nature of the need. Reproduce the format of the slug too: a ticket number first, for instance, taken from the specs, or asked when they give none.
   - No evidence at all: ask one question before creating the branch (see "Asking a question"), recommending `feature/<slug>`. A question of this step comes before the plan folder exists: it and its answer wait in the conversation, and when step 5 creates `interview.md`, write them there under "Git", with the options, your recommendation and the date of the answer. A relaunch after the switch is no longer on the main branch and never asks again: the branch holds the answer.
3. Folder. `<plans_dir>/<YYYY-MM-DD>-<slug>/`: `plans_dir` from `.claude/surface.json`, `docs/plans` when the file or the key is missing; today's date; a short slug of the need, another one if the folder exists. Write `specs.md`: the developer's text as given, or the content of the file their arguments name, verbatim, but for the paths of their machine: a path under a home directory becomes a neutral form such as `/path/to/...`, here and in every answer you write down, since the plan folder is committed and the repository's checks read it. Tell the developer what you replaced. When the specs are in another language than the documents', add their translation below the text, under a heading that says so. Then `surface-status record <plan> plan-opened --json`.
4. Exploration. Before any question, read what the feature touches, as far as the interview needs: the domain objects it extends, the closest precedent (the last thing added the same way), the decisions of step 1 that bear on the area, and what the code already settles of the need, so that no question is asked that the code answers. The path through the code, layer by layer, is left to the agent that drafts the plan. Write `exploration.md` from `${CLAUDE_SKILL_DIR}/templates/exploration.md`, with the findings of step 1, the gates of the plan among them (see "The gates").
5. Interview. List what the specs leave open, then ask (see "Asking a question"), in `interview.md` from `${CLAUDE_SKILL_DIR}/templates/interview.md`. A point is the developer's when it is a rule that a user of the feature, or a program that reads what it writes, would see applied: an order, ties included, a number, a frequency or a limit, who or what is counted or left out, what is refused. What the specs or the code settle, its closest precedent included, is not asked. What neither settles is a question, however obvious its answer looks: your pick is its recommendation, never an assumption of the plan. Stop when what remains is a matter of implementation you can decide, which neither a user nor such a program would see: where the code lives, how the code is named, how a settled result is computed. It goes to the plan as an assumption. Then `surface-status record <plan> interview-closed --json`.
6. Plan. Launch a fresh `Plan` agent (see "The agents") and wait for its return: the plan, whole, since it has no write tool. Write that return to `plan.md` as it is: its design and its form are the agent's, and you rework neither. Two repairs are not a rework, and are not reported to the developer, who never reads the plan: when the markers arrived escaped, `&lt;!--` for `<!--`, the whole return did, and every entity is written as its character, once, since the script reads the markers as literal text; and a path of the machine becomes its path from the root of the repository, or a neutral form such as `/path/to/...` when it lies outside it. Every document you write in the plan folder must pass the gates of step 1, which read it too: a decision still to come or an option set aside is described, never cited by a record number that does not exist. Then check the minimum the chain reads, below, and nothing else. A return that is no plan, or a plan that fails this minimum: launch a fresh agent once more; then tell the developer and stop.
   - The acceptance criteria, numbered, those of the specs and the interview.
   - Each slice behind its `<!-- slice:N -->` marker, alone on its line, and enough for an agent that starts fresh. A slice number the journal has seen is never reused.
   - The `gates` block, which holds the gates you found and no other, in their order: this one you correct yourself (see "The gates").
   - The documents' language, and no code beyond a signature or a schema fragment.
   - For a new revision: every amendment and accepted plan change of `interview.md` carried, and the slices already done kept under their numbers.
7. Extraction. Launch a fresh `surface-extractor` (see "The agents") and wait for its return.
8. Cross-check. Launch a fresh `surface-checker` with the report path `checks/rev-NN-MM.md` and wait for its return. Check that the report exists and opens with the count returned, then `surface-status record <plan> check-done --report checks/rev-NN-MM.md --omissions <k> --json`.
9. Omissions. None: step 10. Otherwise, when `passes.planning` of `show` is more than `passes.ceiling`, stop at the ceiling (see "The agents"). Else read the report and choose: the blueprint must show more, then step 7 with the report's path; or the plan does more than the need, then take that out of `plan.md` yourself and step 7. Then step 8 again. A pass is a cross-check with omissions, which sends the blueprint or the plan back for rework; a clean check costs none. So the blueprint or the plan is reworked `passes.ceiling` times, and the check after them hands back.
10. Draft. `surface-status record <plan> plan-drafted --json`, then "Commit, push and pull request". Refused with the code `gate-list`: `plan.md` lacks its gates block or holds a malformed one; correct it, then step 8.
11. Hand over. Tell the developer where to read the blueprint: its path, and its link in the pull request. At the first hand over of the plan, when `journal.jsonl` holds a single `plan-drafted` line, say in one line how the body of the blueprint is cut, and why, as the extractor returned it, and name the gates the loop will run, `gates` of `show`, or say that the plan names none and the loop then has no objective check. At a later one, say in one line which amendment or decision of `interview.md` the revision carries, and the cut or the gates again only when the revision changed them. The developer is about to read the blueprint: restate neither what it holds nor the plan. Then stay in the conversation and ask: amend, or approve by launching `/surface-execute`, whose launch alone approves this revision.
    - A reply that asks for a change is an amendment: take it as "Taking an amendment" says, which writes it first, records it, draws and cross-checks the next revision, commits and pushes it. Then ask the same question again.
    - A question, about the plan or the blueprint, is answered from the files, and nothing is recorded.
    - In doubt, ask whether the reply is an amendment.
    - A reply that agrees approves nothing: say that the launch of `/surface-execute` approves, and record nothing.

`NN` is the revision: 1 plus the `amendment-received` and `plan-change-accepted` lines of `journal.jsonl`. `MM` is the next pass number not yet taken under `checks/` for that revision. Both on two digits.

## The gates

The plan names the commands that check the whole project, tests, lint, type checks, in its `gates` block. The state script runs them after the slices and at every fix, in order, stopping at the first that fails, within 30 minutes for the whole run. The developer approves them with the plan; only a new revision changes them.

- Find them in step 1, where the project states them: its manifest and build files, its CI workflows, its agent instructions (`AGENTS.md`, `CLAUDE.md`), its README or contributing guide. Prefer the one command that runs them all when there is one, and the order the CI follows.
- Found: write them in `exploration.md` as the gates of the plan, and ask nothing. Found none: ask in the interview which commands check the project, "none" among the options.
- You name the gates, the agent that drafts the plan does not choose them: the `gates` block of `plan.md` holds the commands you found, or those the developer named, and you correct it when the agent wrote others.
- None: the block stays empty, and the plan says in one sentence that the loop has no objective check.
- A command that deploys, publishes, or needs a secret or a service the developer did not name stays out of the block, and the plan says why. So does the chain's own conformity check, which fails until the plan is conformant.

## The agents

A fresh agent for each draft of the plan, each extraction and each cross-check, launched with the Agent tool: `subagent_type` its name, `model` its value in `settings.models` of `show` (`planner`, `extractor`, `checker`), and a prompt of file paths only, never the conversation. The extractor and the checker return a few lines, the `Plan` agent the plan.

- `Plan`, the agent built into Claude Code, which the chain neither installs nor defines: the plan folder; the form of the plan, `${CLAUDE_SKILL_DIR}/templates/plan.md`, to read first, since that file is its whole mandate: what a plan holds, and what to return.
- `surface-extractor`: the plan folder; the form of the blueprint, `${CLAUDE_SKILL_DIR}/templates/blueprint.md`; after a cross-check with omissions, the path of its report.
- `surface-checker`: the plan folder, and the path of the report to write.

If the extractor or the checker returns without its file, launch it once more; then tell the developer and stop.

Stop at the ceiling: once `passes.planning` is more than `passes.ceiling`, or when the script refuses `check-done` with the code `ceiling`, launch nothing more. `surface-status record <plan> blocked --why "<what does not converge>" --json`, commit (see "Commit, push and pull request"), then stay in the conversation: present what does not converge and ask the developer's instruction in the conversation, as "After a block" says for a block during planning, and go on as it says.

## Drafting, the missing step

From `last_event` and the files:

- `interview-closed`, `amendment-received`, `plan-change-accepted`: step 6; step 7 when `plan.md` already carries the last answer, amendment or decision of `interview.md`; step 8 when `blueprint.md` already draws that plan.
- `resumed`: follow the developer's last instruction under "Instructions after a block" in `interview.md`, then step 7 or 8.
- `check-done`: read its line in `journal.jsonl`. No omission: step 10; if the script refuses `plan-drafted` because the check did not cover the current files, step 8. Omissions: step 9, or step 8 when `blueprint.md` already shows what the report lists as missing.

## Taking an amendment

Only in `awaiting-approval`, or `blocked` during execution. The amendment is the developer's input; without one, ask what to change. Write it into `interview.md` under "Amendments", dated, in the developer's words then translated (see "Languages"). Then `surface-status record <plan> amendment-received --json`, then step 6 for the next revision, and on to step 11. The questions it raises are asked as in the interview.

## A plan change proposal

A reviewer found that the blueprint would have to change to stay true, and wrote the proposal at `pending_proposal`. `/surface-execute` puts it to the developer itself when its loop meets it; you take it when the developer launches `/surface-plan` in that state instead. When `interview.md` already holds the decision on this proposal, take it and ask nothing again. Otherwise present it at the level of the blueprint: what would change in it, why, and the proof, not the code. Then ask: accept or refuse, with your recommendation.

- Accepted: write the decision into `interview.md` under "Plan change decisions", then `surface-status record <plan> plan-change-accepted --json`, then step 6: the plan grows slices with new numbers, and a new revision of the blueprint follows.
- Refused: ask the reason in one line and write it into `interview.md`, then `surface-status record <plan> plan-change-refused --why "<reason>" --json`, commit, and invite the developer to relaunch `/surface-execute`: the agents bring the code back to the blueprint, and the next reviewer does not raise the same break again.

## After a block

The loop stopped at the ceiling of autonomous passes; the `blocked` line of `journal.jsonl` says why. It stopped during planning when the journal holds no `plan-approved` after its last `interview-closed`, `amendment-received` or `plan-change-accepted`; otherwise during execution.

- During planning: present what does not converge, from the last reports under `checks/`, and ask the developer's instruction in the conversation. Write it into `interview.md` under "Instructions after a block", then `surface-status record <plan> resumed --json`, and resume at the missing step. An instruction that amends the plan is taken as an amendment instead.
- During execution: the loop handed back and the developer revises the plan: take the amendment. If they only want the loop to go on, `/surface-execute` resumes it: say so and stop. When `pending_suspicion` of `surface-status show <plan> --json` is not null, name that suspected break and its reason too: an amendment drops it, a resumption hands it to a reviewer.

## Not your turn

The developer amends a plan only when it is their turn: awaiting approval, or blocked. While the agents work (`executing`, `reviewing`, `fixing`), explain that no amendment is taken now, record nothing, and offer the two ways: wait for the loop to stop, then relaunch `/surface-plan`; or abandon the plan with `/surface-status`.

## Commit, push and pull request

- Commit only the files of the plan folder, by path, following the repository's conventions. Each journal line goes in the commit of the files it describes. Never other changes of the working tree.
- Before the first push of the branch (it has no upstream yet), read the CI configuration. If its triggers react to a push of this branch or to the opening of a pull request, draft included, warn the developer, say what would run, and wait for their agreement. Write their answer into `interview.md` under "Git", so a relaunch does not ask again. Declined: push nothing, say the plan is committed locally, and go to step 11.
- Push the branch, setting its upstream.
- The pull request opens as a draft at the first `plan-drafted`. Its description is the text `surface-status pr-body` prints, and nothing else (it takes no argument, since it describes every plan of the branch): the output of the script is given to `gh` on its standard input, so that no text of yours stands between the two. No pull request yet: `gh pr create --draft --body-file -`, with a title after the repository's conventions. One exists: `gh pr edit --body-file -`. Refresh it the same way at the end of every launch that pushes.
- Nothing else is written on the pull request, and you never mark it ready for review. Its comments are read only when the developer asks for it explicitly.
- Without `gh` or a remote, say so, give the description, and stop after the commit.

## What the developer gave

$ARGUMENTS
