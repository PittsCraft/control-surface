# 0022. Each agent role is a leaf

Status: accepted
Date: 2026-09-29

## Context

The four roles (extractor, checker, executor, reviewer) are launched fresh by a command, given file paths, and return a few lines. The Claude Code documentation of subagents (checked on 2026-09-29) says a definition without `tools` inherits every tool available to subagents, `Agent` included, and that a subagent may spawn subagents of its own unless `Agent` is left out of its `tools`. It also offers `isolation: worktree`, which runs the subagent in a temporary worktree branched from the default branch, and `permissionMode`.

## Decision

Every definition lists its `tools`, and none lists `Agent` (or its former name `Task`): a role does its mandate itself. The extractor has `Read, Glob, Grep, Write, Edit`; the checker `Read, Glob, Grep, Write`; the reviewer `Read, Glob, Grep, Write, Bash`, for git and the state script, and no `Edit`; the executor `Read, Glob, Grep, Edit, Write, Bash`.

No definition sets `isolation`: the work of a slice must stay on the branch, visible to the next step, and uncommitted work found on resumption is read by the next executor. No definition sets `permissionMode`: the host decides what runs unattended.

The frontmatter holds `name`, `description`, `tools`, `model` and, for the judgment roles, `effort`, one `key: value` per line; a test refuses any other field.

## Consequences

A role that needs a tool it lacks fails visibly instead of borrowing one. The prompts, not the tool lists, keep the reviewer and the checker off the code, since `Write` can write anywhere; the end to end runs watch for it. Adding a field to a definition means changing the frontmatter test and this record.
