# 0034. Gates named by the plan, no settings file at install

Status: accepted
Date: 2026-09-29

## Context

Without `gate_command` the gates counted as green and the loop had no objective check, so a developer had to find and write their gate command. The installer also created `.claude/surface.json` and `.claude/surface.md` in the host.

## Decision

- `/surface-plan` finds the commands that check the project (manifest, build files, CI workflows, `AGENTS.md`, `CLAUDE.md`) and writes them in a `gates` fenced block of `plan.md`, one per line. It asks only when it finds none. An empty block says the project has none.
- `plan-drafted` carries the commands of the block (ADR 0012) and is refused (`gate-list`) without a readable block. `plan-approved` pins those of the drafted revision: an edit of `plan.md` after approval changes nothing, and a `plan-amended` that changes the block is refused.
- `gate` runs them in order, stops at the first failure, writes one report and answers each result under `commands`, within a fixed 30 minutes for the whole run. `show` names them under `gates`.
- A plan approved before this change has no pinned gates: it runs none, as a project without `gate_command` did.
- `gate_command`, `gate_timeout_minutes` and `mark_pr_ready` are refused with what replaced them. The agents read `AGENTS.md` or `CLAUDE.md` instead of `surface.md`. The installer creates no settings file, deletes none, and names what an earlier version left.

## Consequences

A one-line install, then `/surface-plan` and `/surface-execute`, need no file written by the developer. The developer is shown the gates at hand over and at approval. Changing a gate takes a new revision.
