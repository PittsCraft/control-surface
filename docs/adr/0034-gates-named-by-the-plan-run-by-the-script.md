# 0034. Gates named by the plan, run by the script

Status: accepted
Date: 2026-09-29

## Context

An agent can declare a success it has not verified; an exit code is a fact. The chain therefore runs the project's gates itself. The gate command first came from a `gate_command` setting in `.claude/surface.json`, which the installer created. Without it the gates counted as green and the loop had no objective check, so a developer had to find and write their command before the chain did anything useful.

## Decision

- `/surface-plan` finds the commands that check the project (manifest, build files, CI workflows, `AGENTS.md`, `CLAUDE.md`) and writes them in a `gates` block of `plan.md`, one per line. It asks only when it finds none; an empty block says the project has none.
- `plan-drafted` carries the commands of the block and is refused (`gate-list`) without a readable one. `plan-approved` pins those of the approved revision: a later edit of `plan.md` changes nothing, and a `plan-amended` that changes the block is refused. Changing a gate takes a new revision.
- `surface-status gate` is the only writer of `gates-run`. It first submits the failed run it would record to the guards, and runs nothing when that would be refused, in a state that takes no run or at the ceiling. Otherwise it runs the commands in order through `/bin/sh -c`, each in its own process group killed when it ends, stops at the first failure, kills the running group after 30 minutes for the whole run, writes `gates/run-NN.txt`, then records the result. A timeout is a failure, and a failed run costs a pass.
- The settings `gate_command`, `gate_timeout_minutes` and `mark_pr_ready` are refused with what replaced them. A plan approved before this change has no pinned gates and runs none.

## Consequences

A one-line install, then `/surface-plan` and `/surface-execute`, need no file written by the developer, who is shown the gates at hand over and at approval. No gate run is spent on a result the journal would refuse. A process that leaves its session on purpose escapes the kill.
