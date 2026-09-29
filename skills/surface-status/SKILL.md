---
name: surface-status
description: Says where the plans of the project stand and details one of them, runs the conformity check, and abandons a plan once the developer confirms. Takes a plan folder, `check`, or `abandon` with an optional plan folder.
argument-hint: "[plan] | check | abandon [plan]"
disable-model-invocation: true
allowed-tools: Bash(.claude/skills/surface-status/scripts/surface-status *) Bash(git add *) Bash(git commit *) Bash(git push *) Bash(gh pr edit *)
---

# surface-status

You tell the developer where the plans stand, from the state script alone, and you record one act of theirs: the abandonment of a plan, once they have confirmed it. Every other act belongs to `/surface-plan` or `/surface-execute`: name the one to run, and record nothing else.

The state script is `.claude/skills/surface-status/scripts/surface-status`, run from the root of the repository; below it is written `surface-status`, and `<plan>` is the plan folder. It is the only writer of the journal, and the same script the project's CI calls. Exit code 0 is accepted, 1 refused or check failed with the reason, 2 a usage error. The state lives in files: read it from the script at each step, never from memory of this conversation.

Every command runs from the root of the repository, with paths from there: never `cd`, since the shell is shared with the agents and a `cd` followed by git stops for an approval, nor `git -C`, which the permission rules do not read as the git command it runs. Plain commands only, which the developer's permission rules can read: no variable or function standing for a command, no command run by another such as `find -exec`, no expansion such as `$?` or `$(...)`, no here-document; the exit code comes back with the result, never echo it.

## What the developer asked

Their arguments, empty when none: $ARGUMENTS

- Nothing: run `surface-status`, the plans of the branch with their state and who has the hand. When exactly one of them is in progress, add its detail, as for a plan.
- A plan: `surface-status show <plan>`: its state, who has the hand, the next step, the slices done and left, the passes used against the ceiling, the effective settings. Then name the command that takes the next step.
- `check`: `surface-status check --require conform`, the conformity check to run before merging. On a failure, say which plans fail and why. For a plan abandoned after its approval, the alarm stays even if its code was removed, since the script cannot see code: the developer removes that code or merges knowingly.
- `abandon`, with or without a plan: see "Abandoning a plan".

Relay what the script answers, without adding to it beyond the command to run next.

## Abandoning a plan

1. The plan: the one named. Otherwise `surface-status show --json`, which takes the only plan of the branch in progress, or exits 2 naming the candidates: then ask the developer which one, and stop.
2. `surface-status show <plan> --json`. A plan `conform` or `abandoned` is over: say so, and stop.
3. Ask the developer to confirm, in one message: the plan and its state; that abandoning is final, no command acts on the plan again; and, when the journal holds a `plan-approved`, that the conformity check fails from then on, since the branch may carry code never declared conform, and that the alarm stays even if that code is removed. Ask for the reason, on one line. Record nothing without an explicit yes.
4. Confirmed: read the state again with `surface-status show <plan> --json`, since the files decide and not the conversation, then `surface-status abandon <plan> --why "<reason>"`.
5. Commit the journal alone, by pathspec, following the repository's commit conventions. Push the branch when it has an upstream. Refresh the pull request's description: the output of `surface-status pr-body` (it takes no argument, since it describes every plan of the branch), given to `gh pr edit --body-file -` on its standard input. Without a pull request or without `gh`, say so.
