# 0015. Main branch detection, and the plan that `resolve` designates

Status: accepted
Date: 2026-09-29

## Context

An agent never guesses a slug. It needs the plan of the branch it is on, or a list to show the developer, and it needs to know which commits of the branch belong to which plan. Everything hangs on the main branch: the plans of a branch are the folders it adds against its merge base with main.

## Decision

The main branch is `origin/HEAD` when it exists and points at a commit, else the local `main`, else the local `master`, else `origin/main`, else `origin/master`. The last two serve a CI checkout of a pull request: it is detached, has no local branch and may have no `origin/HEAD`, but it holds the remote branch. No setting is added, and none can be: a repository with none of the five is a usage error (exit 2) that says what was looked for. The merge base is that of the main branch and `HEAD`; when it cannot be found (a shallow clone), the error says the full history is needed.

`resolve --for plan|execute [plan]`:

1. An explicit plan wins, whatever its state and wherever it is (path or name under the plans directory, as everywhere).
2. Otherwise the plans of the branch (ADR 0016) whose state the command accepts: `surface-plan` sees `interview`, `drafting`, `awaiting-approval`, `plan-change-proposed` and `blocked`; `surface-execute` sees `awaiting-approval`, `executing`, `reviewing`, `fixing`, and `blocked` only when the loop stopped during the execution. A journal with no event yet is a plan to open, seen by `surface-plan` only. A terminal plan is seen by nobody.
3. From the main branch, the unmerged branches are scanned too, and their plans that the command accepts are listed with the command that switches to them.

`show` and `abandon` without a plan use the same selection with any state that is not terminal, and exit 2 naming the candidates when there are none or several.

Exit codes: 0 when one plan is designated (explicitly or not), 1 when none or several match, a verdict the skill turns into a question, 2 when the call is wrong (unknown plan, no main branch, an unreadable journal on the branch). The text answer is the plan name alone on standard output when one is found; otherwise the explanation goes to standard error. With `--json`: `ok`, `for`, `outcome` (`explicit`, `one`, `several` or `none`), `branch`, `plan` (null unless one is designated), `candidates` and `other_plans` (each `{name, state}`: the plans of the branch that match the command, and those in progress that do not), `elsewhere` (each `{branch, plan, state, suggestion}`, plus `error` when the journal of that branch could not be read).

Outside a git work tree there is no branch: every plan folder that holds a journal counts, as before.

## Consequences

`list` and `check` work on the plans of the branch too, which is what the conformity check of a pull request needs, and plans kept on main after earlier merges no longer make it fail. A plan an agent must act on is found by asking, never by reading folder names. A decision that hangs on the state (several candidates) is handed to the developer with the list.
