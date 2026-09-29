# 0019. Ownership by namespace

Status: accepted
Date: 2026-09-29

## Context

The installer must update what it installed, remove what the source dropped, and leave every other file of the host alone, without a manifest that someone has to keep in step with the sources.

## Decision

The installer owns `.claude/skills/surface-*/` (every file below) and `.claude/agents/surface-*.md`. Nothing else is written, replaced or removed. A source skill or agent outside the `surface-` prefix is not installed. `.claude/surface.json` and `.claude/surface.md` are created from `templates/` when nothing exists at their path, and never touched afterwards, whatever they hold. `.claude/settings.json` is never read or written. Bytecode (`__pycache__`, `.pyc`, `.pyo`) and `.DS_Store` are never copied and never reported, so running the script in a host does not create drift.

Before writing or removing anything, the installer refuses (exit 2, nothing written) when a file it would overwrite or remove is modified, staged or not tracked by git, naming the files; `--force` overrides. Outside a git work tree the guard does not apply. It never removes a file outside the namespace.

## Consequences

A file added to `skills/surface-*` or `agents/surface-*.md` ships without any registration. A host that wants its own agent or skill uses another prefix. A test asserts that settings survive byte for byte under arbitrary content.
