# control-surface

Approve a short overview of your feature, then let agents build it and review their own work until it matches, without reading the code yourself.

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
- It explores the code the feature touches, then asks you its questions one at a time. Each comes with its options and the one it would pick. Your answers are written down as you give them, and it never invents a business rule to fill a gap.
- It finds the commands that check your project, tests, lint, type checks, where your project states them, and writes them in the plan as its gates. It asks you only if it finds none.
- It writes a detailed plan, then draws a concise overview from it and has it cross-checked, so that the overview hides nothing the plan does.
- Before the first push, if your CI reacts to a push or to a new PR, it warns you and waits for your agreement.
- It commits, pushes, opens a draft PR that links the overview and the plan, and tells you where to read the overview and which gates the loop will run.

Everything lands in one folder per plan, `docs/plans/<date>-<slug>/` by default.

### 2. Read the overview, amend or approve

`overview.md` is the only thing you have to read. It shows what will be built, in fixed sections, with diagrams where they help: the idea in one sentence, acceptance criteria, scope, data, boundaries, sequences, state machines, algorithms, and the sensitive zones, the points that touch your control, your work or your time and that you did not see go by. It does not show the order of construction: that stays in the plan.

- To change something, say what in the conversation: `/surface-plan` keeps the hand after it hands over. It records your amendment, produces the next revision of the plan and of the overview, then asks again. A question is answered and changes nothing. In a new session, run `/surface-plan` with your amendment.
- To approve, run `/surface-execute`. Launching it counts as approval, gates included: it names the plan, the revision and the gates it approves, then freezes the overview. No sentence of the conversation approves a revision.

### Permissions

The loop runs until a command needs an approval your rules or mode do not give, then waits for you. How much it does alone is your call: auto mode on your machine, `bypassPermissions` only in a container or a VM you can throw away, or the default mode with your own allow rules.

### 3. Let the agents work

`/surface-execute` hands each slice of the plan to a fresh agent. Then it runs the gates of the plan, in order, stopping at the first that fails, has a fresh agent review everything the branch changes against the overview, and has defects fixed, pass after pass. When the code departs from the plan but the overview stays true, the plan is amended and the work goes on.

The reviewer raises only what concerns correctness or the requirements, never a style preference. Your own commits on the branch are reviewed too, and may be fixed.

While the agents work, you do not amend the plan: you wait for the loop to stop, or you abandon the plan.

`/surface-execute` dispatches soundly on any model. The agents run on the models of `.claude/surface.json`, or its defaults, whatever your session's.

### 4. When you get the hand back

The loop hands back in three cases, tells you in the terminal, and in the first two asks you what to do in the conversation.

| What stopped it | What you find | What you do |
|---|---|---|
| A contract break: the overview would have to change to stay true | a plan change proposal, in `plan-changes/`, presented at the level of the overview | Decline it with a reason in one line: the loop goes on, the agents bring the code back to the overview and do not raise the same break again. Accept it, then run `/surface-plan`, which draws the new revision for you to approve with `/surface-execute`. |
| The ceiling of autonomous passes, three by default | a summary of what does not converge | Answer that it resumes: the loop goes on in the session with a fresh count. Or amend the plan with `/surface-plan <amendment>`. |
| The conform state | one line that says so, and an updated PR description | Mark the PR ready when you want: step 5. |

### 5. Mark the PR ready, then merge

Conform means the last review proved every acceptance criterion of the overview you approved: a criterion it cannot prove is a finding, and the loop goes on. Nothing is left for you to check. The proof stays in `conformity.md`, each criterion with a test, a file and line or a gate result, for whoever wants it.

The PR description lists, one line each and for information, the decisions the agents took within the contract that you did not see go by: the plan amendments that keep the overview true, and the suspected breaks a reviewer dismissed. It lists nothing when there is nothing to list.

When you want, you mark the PR ready for review, which triggers your CI, and you merge. The chain never does it for you. The conformity check belongs in your CI when the PR is marked ready, and in your hands before merging:

```sh
.claude/skills/surface-status/scripts/surface-status check --require conform
```

It fails as long as a plan of the branch is neither conform nor abandoned before its approval, so keep it out of the gates your plans name.

In a GitHub Actions workflow, the check needs the full history of the repository to find where your branch left the main branch. A checkout at depth 1, the default, makes it exit 2 and say so:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]

jobs:
  conformity:
    # A draft pull request waits until it is marked ready.
    if: ${{ !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: .claude/skills/surface-status/scripts/surface-status check --require conform
```

Exit code 0 means every plan of the branch is conform, 1 that one is not, 2 that the check could not run.

### At any time: `/surface-status`

It lists your plans, their state and who has the hand, and details one plan: its next step, the slices left, the passes used. It also abandons a plan, after asking you to confirm. A plan abandoned after approval makes the conformity check fail, since the branch carries code never declared conform: you then merge knowingly.

### Interrupted? Relaunch the same command

The whole state lives in the plan folder, in your repository. If a session dies at any step, relaunch the same command in a new session: it resumes where it stopped, without asking a question again or losing an amendment. Without an argument, it finds the plan of the current branch that fits, and asks you if several do.

On resumption, uncommitted work is taken as the interrupted step's: a fresh agent rereads it, then continues or undoes it. If that work is yours, it runs the same risk.

## A session, in short

A sketch of the gestures, not a transcript:

```text
you      /surface-plan Add a CSV export to the invoices page
agent    explores the code, then asks its questions one at a time, each with a recommended option
you      answer them
agent    writes the plan and the overview, pushes the branch, opens a draft PR
you      read overview.md, then ask for changes in the conversation, or run /surface-execute to approve
agents   slices, gates, review, fixes, until conform or until they hand back
you      mark the PR ready when you want, merge
```

## Settings

The chain needs no configuration: the gates are found at planning and approved with the plan, and the agents read your critical zones and conventions in your `AGENTS.md` or `CLAUDE.md`. To tune something, write `.claude/surface.json` with any of `plans_dir` (`docs/plans`), `max_autonomous_passes` (`3`) and `models` (`opus` for the judgment roles, `sonnet` for the executor). During execution, a pass is one time the loop sends work back to an agent on its own, to fix a review's findings or a failed gate run, or to resume a slice after a dismissed suspicion; a clean review or a green gate run costs none.

## Update and drift check

Update the chain by running the install command again. Check that the installed chain matches the source, without writing anything (exit code 1 on drift):

```sh
curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py | python3 - --check
```

## How it works

Each plan keeps a journal that only a state script writes. The script refuses any illegal step, for example an approval when the overview changed since its cross-check, or any further work once the approved overview has been modified. Each slice, review and fix goes to a fresh agent that reads files, never a conversation. The installer owns only the chain's files under `.claude/`, and refuses to overwrite one that holds uncommitted changes unless you pass `--force`.

The architecture is described in [ARCHITECTURE.md](ARCHITECTURE.md), and the decisions whose history matters in [`docs/adr/`](docs/adr/README.md). To work on the chain itself, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT, see `LICENSE`.
