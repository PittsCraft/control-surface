# control-surface

Approve a short overview of your feature, then let agents build it and review their own work until it matches, without reading the code yourself.

```sh
curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py | python3 -
```

Run it at the root of your project. It installs the chain in `.claude/`, with its three commands, `/surface-plan`, `/surface-execute` and `/surface-status`, and creates two settings files that stay yours. It never writes your Claude Code settings: [Permissions](#permissions) says what to allow. Add `--ref <tag or commit>` to pin a version.

## Prerequisites

Claude Code, git, Python 3.11 or newer, and `curl` for the one-line install. The GitHub CLI, `gh`, opens and updates the pull request.

## Your path, from need to merge

### 1. Plan: `/surface-plan`

In a Claude Code session of your project, run `/surface-plan` with a short description of what you need.

- From the main branch, it creates a branch that follows your repository's conventions. From any other branch, it opens the plan there, so one branch can carry several plans.
- It explores the code the feature touches, then asks you its questions one at a time. Each comes with its options and the one it would pick. Your answers are written down as you give them, and it never invents a business rule to fill a gap.
- It writes a detailed plan, then draws a concise overview from it and has it cross-checked, so that the overview hides nothing the plan does.
- Before the first push, if your CI reacts to a push or to a new PR, it warns you and waits for your agreement.
- It commits, pushes, opens a draft PR that links the overview and the plan, and tells you where to read the overview.

Everything lands in one folder per plan, `docs/plans/<date>-<slug>/` by default.

### 2. Read the overview, amend or approve

`overview.md` is the only thing you have to read. It shows what will be built, in fixed sections, with diagrams where they help: the idea in one sentence, acceptance criteria, scope, data, boundaries, sequences, state machines, algorithms, and the sensitive zones, the points that touch your control, your work or your time and that you did not see go by. It does not show the order of construction: that stays in the plan.

- To change something, run `/surface-plan` again and say what. It records your amendment and produces the next revision of the plan and of the overview.
- To approve, run `/surface-execute`. Launching it counts as approval: it names the plan and the revision it approves, then freezes the overview.

### Permissions

Before your first `/surface-execute`, allow what the loop runs. The agents work unattended: a command that waits for an approval stops the agent that asked, and the loop with it. Add these rules once per project, to `.claude/settings.json` to share them with your team or to `.claude/settings.local.json` to keep them to yourself, merged into `permissions.allow` if the file already has one:

```json
{
  "permissions": {
    "allow": [
      "Bash(.claude/skills/surface-status/scripts/surface-status *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git push *)",
      "Bash(git rm *)",
      "Bash(git mv *)",
      "Bash(git restore *)",
      "Bash(git revert *)",
      "Bash(gh pr view *)",
      "Bash(gh pr edit *)",
      "Bash(gh pr ready *)",
      "Bash(npm test *)"
    ]
  }
}
```

The last rule is an example: name your gate command, the `gate_command` of `.claude/surface.json`, and the narrower checks an agent runs on a slice if they differ. Accept file edits too, for the session (`Shift+Tab` until "accept edits on") or from the start (`claude --permission-mode acceptEdits`). Read-only commands such as `ls`, `grep` or `git log` need no rule.

The commands grant some of these tools themselves, in their `allowed-tools`, but that grant holds only for the turn you launch them in and clears at the next message. The agents run under your session's rules, and when an agent hands back asynchronously, the loop goes on in a later turn, without the grant. No command checks your rules at launch: they come from several settings files and from the command line, and a session cannot read which ones are in force.

### 3. Let the agents work

`/surface-execute` hands each slice of the plan to a fresh agent. Then it runs your gates, if you declared them, has a fresh agent review everything the branch changes against the overview, and has defects fixed, pass after pass. When the code departs from the plan but the overview stays true, the plan is amended and the work goes on.

The reviewer raises only what concerns correctness or the requirements, never a style preference. Your own commits on the branch are reviewed too, and may be fixed.

While the agents work, you do not amend the plan: you wait for the loop to stop, or you abandon the plan.

The command runs on Sonnet, and with its own grants, only in the turn you launch it in. An agent often hands back asynchronously, and the loop then goes on in a later turn, on your session's model: it says so when it stops. To keep the whole loop in its first turn, start the session with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 claude`, which runs every agent in the foreground and turns off the other background tasks of that session.

### 4. When you get the hand back

The loop stops in three cases, and tells you in the terminal.

| What stopped it | What you find | What you do |
|---|---|---|
| A contract break: the overview would have to change to stay true | a plan change proposal, in `plan-changes/` | Run `/surface-plan`, which presents it at the level of the overview. Accept it, and you get a new revision to approve. Refuse it with a reason, then relaunch `/surface-execute`: the agents bring the code back to the overview and do not raise the same break again. |
| The ceiling of autonomous passes, three by default | a summary of what does not converge | Relaunch `/surface-execute` to continue with a fresh count, or amend the plan with `/surface-plan`. |
| The conform state | `conformity.md`, and an updated PR description | Go to step 5. |

### 5. Check the proof, then merge

`conformity.md` lists each acceptance criterion of the overview and what proves it holds: a test, a file and line, a gate result. You check it against the overview you approved, not against the code.

Then you mark the PR ready for review, which triggers your CI, and you merge. The conformity check belongs in your CI when the PR is marked ready, and in your hands before merging:

```sh
.claude/skills/surface-status/scripts/surface-status check --require conform
```

It fails as long as a plan of the branch is neither conform nor abandoned before its approval, so keep it out of your gate command.

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
you      read overview.md, then /surface-plan with an amendment, or /surface-execute to approve
agents   slices, gates, review, fixes, until conform or until they hand back
you      read conformity.md against overview.md, mark the PR ready, merge
```

## Settings

`.claude/surface.json` holds what you can tune per project:

| Setting | Default | |
|---|---|---|
| `plans_dir` | `docs/plans` | where plan folders go |
| `max_autonomous_passes` | `3` | how far the agents go before handing back |
| `gate_command` | none | the command that runs your full gates, none to do without |
| `gate_timeout_minutes` | `30` | its timeout |
| `models` | `opus` for the three judgment roles, `sonnet` for the executor | the model of each agent |
| `mark_pr_ready` | `false` | let the command mark the PR ready instead of you |

`.claude/surface.md` is free text read by the agents: your critical zones, your conventions, anything they should know about the project.

Both files belong to your project. Installing or updating creates them when missing and never overwrites them.

## Update and drift check

Update the chain by running the install command again. Check that the installed chain matches the source, without writing anything (exit code 1 on drift):

```sh
curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py | python3 - --check
```

## How it works

Each plan keeps a journal that only a state script writes. The script refuses any illegal step, for example an approval when the overview changed since its cross-check, or any further work once the approved overview has been modified. Each slice, review and fix goes to a fresh agent that reads files, never a conversation. The installer owns only the chain's files under `.claude/`, and refuses to overwrite one that holds uncommitted changes unless you pass `--force`.

The design decisions, each with its context and its consequences, are in [`docs/adr/`](docs/adr/). To work on the chain itself, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT, see `LICENSE`.
