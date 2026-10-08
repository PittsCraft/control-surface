# Guide

The manual of the chain: every step from a need to a merged pull request, and what to tune. The idea behind it is in the [README](../README.md).

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py | python3 -
```

Run it at the root of your project. It installs the chain in `.claude/`, with its three commands, `/surface-plan`, `/surface-execute` and `/surface-status`, and needs no configuration. It never writes your Claude Code settings. Add `--ref <tag or commit>` to pin a version.

## Prerequisites

Claude Code, git, Python 3.11 or newer, and `curl` for the one-line install. The GitHub CLI, `gh`, opens and updates the pull request.

## Your path, from need to merge

### 1. Plan: `/surface-plan`

In a Claude Code session of your project, run `/surface-plan` with a short description of what you need. It runs on your session's model and effort: Opus with the effort `high` is recommended (`/model opus`, `/effort high`).

- From the main branch, it creates a branch named after your repository's practice: a written convention, else the branches of your past pull requests, and it asks you when it finds none. From any other branch, it opens the plan there, so one branch can carry several plans.
- It explores the code the feature touches, then asks you its questions one at a time. Each comes with its options and the one it would pick. Your answers are written down as you give them, and it never invents a business rule to fill a gap. A rule a user of the feature would see applied, an order, a number, a limit, is yours to decide: it asks unless your specs or your code already settle it, and settles alone only what is a matter of implementation.
- It finds the commands that check your project, tests, lint, type checks, where your project states them, and writes them in the plan as its gates. It asks you only if it finds none.
- It has a detailed plan drafted by the `Plan` agent built into Claude Code, then the blueprint drawn from it and cross-checked, so that the blueprint hides nothing the plan does.
- It commits, pushes, opens a draft PR that links the blueprint and the plan, and tells you where to read the blueprint and which gates the loop will run.

Everything lands in one folder per plan, `docs/plans/<date>-<slug>/` by default.

### 2. Read the blueprint, amend or approve

`blueprint.md` is your control surface, and the only thing you have to read. It holds every decision that matters, and is as long as the feature needs and no longer. It always opens with the idea in one sentence, the acceptance criteria and the scope, and closes with the sensitive zones: first the critical zones you declared that the plan touches, by name, or that it touches none, then the points that touch your control, your work or your time and that you did not see go by. Between them, what will be built is cut for the feature, by flow, by component or by decision, with a diagram wherever one is clearer than prose. Its last line names what the feature leaves alone among the data schema, the boundaries, the sequences, the state machines and the algorithms, so you see it at a glance. A revision keeps the cut of the one before, and you can ask for another cut like any other change. It does not show the order of construction: that stays in the plan. A rule the plan had to settle on its own, since neither your specs, your answers nor your code settle it, is marked on the blueprint as an assumption of the plan: approving the blueprint confirms it, and you correct a wrong one like any other change. A critical zone counts as touched as soon as the plan changes a file that holds its code, even when the rule it protects stays as it is: the blueprint names that file and says how far the change goes, so you learn at approval which files you will read. The list you are given once the work conforms is the reference: a fix after your approval may add to it another file of a zone the blueprint named. A change that reaches a zone the blueprint said was not touched comes back to you first, like any change that would make the blueprint false.

- To change something, say what in the conversation: `/surface-plan` stays in the conversation after it hands over. It records your amendment, produces the next revision of the plan and of the blueprint, then asks again. A question is answered and changes nothing. In a new session, run `/surface-plan` with your amendment.
- To approve, run `/surface-execute`. Launching it counts as approval, gates included: it names the plan, the revision and the gates it approves, then freezes the blueprint. No sentence of the conversation approves a revision.

### Permissions

The loop runs until a command needs an approval your rules or mode do not give, then waits for you. How much it does alone is your call: auto mode on your machine, `bypassPermissions` only in a container or a VM you can throw away, or the default mode with your own allow rules.

### Attribution

Claude Code ends every commit a session makes with a `Co-Authored-By` line by default, and the commits of the chain's agents carry it like any other. The chain says nothing of it: its agents write a commit after your repository's conventions, and whether your history names an assistant is your call, in your Claude Code settings. To turn it off for every session of your project, add this to your `.claude/settings.json`:

```json
{
  "attribution": {
    "commit": "",
    "pr": ""
  }
}
```

`commit` hides the line on the commits, and `pr` the one Claude Code adds to a pull request description. Do it before your first plan when a commit hook of yours refuses an attribution: each agent would otherwise meet that refusal at its commit. The chain does not do it for you, since its installer never writes your Claude Code settings.

### 3. Let the agents work

`/surface-execute` hands each slice of the plan to a fresh agent. Then it runs the gates of the plan, in order, stopping at the first that fails, has a fresh agent review everything the branch changes against the blueprint, and has defects fixed, pass after pass. When the code departs from the plan but the blueprint stays true, the plan is amended and the work goes on.

The reviewer raises only what concerns correctness or the requirements, never a style preference. Your own commits on the branch are reviewed too, and may be fixed.

While the agents work, you do not amend the plan: you wait for the loop to stop, or you abandon the plan.

`/surface-execute` dispatches soundly on any model. The agents run on the models of `.claude/surface.json`, or its defaults, whatever your session's.

### 4. When the loop hands back to you

The loop hands back in three cases, tells you in the terminal, and in the first two asks you what to do in the conversation.

| What stopped it | What you find | What you do |
|---|---|---|
| A contract break: the blueprint would have to change to stay true | a plan change proposal, in `plan-changes/`, presented at the level of the blueprint | Decline it with a reason in one line: the loop goes on, the agents bring the code back to the blueprint and do not raise the same break again. Accept it, then run `/surface-plan`, which draws the new revision for you to approve with `/surface-execute`. |
| The ceiling of autonomous passes, three by default | a summary of what does not converge | Answer that it resumes: the loop goes on in the session with a fresh count. Or amend the plan with `/surface-plan <amendment>`. |
| The conformant state | one line and nothing else: it says so, names the files your branch changed in your critical zones, when there are any, and ends on your step; and an updated PR description | Mark the PR ready when you want: step 5. When the chain could open no PR, without `gh` or a remote, that line tells you to open it, and how to print its description. |

### 5. Mark the PR ready, then merge

Conformant means the last review proved every acceptance criterion of the blueprint you approved: a criterion it cannot prove is a finding, and the loop goes on. Nothing is left for you to check, except the code of the critical zones your `AGENTS.md` or `CLAUDE.md` declares: the PR description lists the files the branch changed there, for you to read yourself. The proof stays in `conformity.md`, each criterion with a test, a file and line or a gate result, for whoever wants it.

The PR description lists, one line each and for information, the decisions the agents took within the contract that you did not see go by: the plan amendments that keep the blueprint true, and the suspected breaks a reviewer dismissed. It lists nothing when there is nothing to list.

When you want, you mark the PR ready for review, and you merge. The chain never does it for you. Before merging, the conformity check is in your hands:

```sh
.claude/skills/surface-status/scripts/surface-status check --require conformant
```

It fails as long as a plan of the branch is neither conformant nor abandoned before its approval, so keep it out of the gates your plans name. Exit code 0 means every plan of the branch is conformant, 1 that one is not, 2 that the check could not run.

Your CI can call it too: whether it does, and when, is yours to decide. It needs the full history of the repository, main branch included, to find where your branch left it: in a checkout that is shallow, or that holds your branch alone, it exits with 2.

### At any time: `/surface-status`

It lists your plans, their state and whose turn it is, and details one plan: its next step, the slices left, the passes used. It also abandons a plan, after asking you to confirm. A plan abandoned after approval makes the conformity check fail, since the branch carries code never declared conformant: you then merge knowingly.

### Interrupted? Relaunch the same command

The whole state lives in the plan folder, in your repository. If a session dies at any step, relaunch the same command in a new session: it resumes where it stopped, without asking a question again or losing an amendment. Without an argument, it finds the plan of the current branch that fits, and asks you if several do.

On resumption, uncommitted work is taken as the interrupted step's: a fresh agent rereads it, then continues or undoes it. If that work is yours, it runs the same risk.

## A session, in short

A sketch of who does what, not a transcript:

```text
you      /surface-plan Add a CSV export to the invoices page
agent    explores the code, then asks its questions one at a time, each with a recommended option
you      answer them
agent    writes the plan and the blueprint, pushes the branch, opens a draft PR
you      read blueprint.md, then ask for changes in the conversation, or run /surface-execute to approve
agents   slices, gates, review, fixes, until the plan is conformant or until they hand back
you      mark the PR ready when you want, merge
```

## Settings

The chain needs no configuration: the gates are found at planning and approved with the plan, and the agents read your critical zones and conventions in your `AGENTS.md` or `CLAUDE.md`. To tune something, write `.claude/surface.json` with any of `plans_dir` (`docs/plans`), `max_autonomous_passes` (`3`) and `models` (`opus` for the `planner` and the judgment roles, `sonnet` for the `executor`). During execution, a pass is one time the loop sends work back to an agent on its own, to fix a review's findings or a failed gate run, or to resume a slice after a dismissed suspicion; a clean review or a green gate run costs none. During planning, a pass is a cross-check that finds omissions, which sends the blueprint or the plan back for rework; a clean check costs none. In both, the loop sends work back `max_autonomous_passes` times on its own, and hands back to you at the pass after them.

## Update and drift check

Update the chain by running the install command again. Check that the installed chain matches the source, without writing anything (exit code 1 on drift):

```sh
curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py | python3 - --check
```

## How it works

Each plan keeps a journal that only a state script writes. The script refuses any illegal step, for example an approval when the blueprint changed since its cross-check, or any further work once the approved blueprint has been modified. Each slice, review and fix goes to a fresh agent that reads files, never a conversation. The installer owns only the chain's files under `.claude/`, and refuses to overwrite one that holds uncommitted changes unless you pass `--force`.

The architecture is described in [ARCHITECTURE.md](../ARCHITECTURE.md), and the decisions whose history matters in [`docs/adr/`](adr/README.md). To work on the chain itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
