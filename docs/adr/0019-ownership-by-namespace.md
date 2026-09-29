# 0019. Ownership by namespace

Status: accepted
Date: 2026-09-29

## Context

The installer must update what it installed, remove what the source dropped, and leave every other file of the host alone, without a manifest that someone has to keep in step with the sources. Earlier versions also created `.claude/surface.json` and `.claude/surface.md` in the host.

## Decision

The installer owns `.claude/skills/surface-*/` and `.claude/agents/surface-*.md`, and nothing else is written, replaced or removed. It creates no settings file and never reads or writes `.claude/settings.json`; it only names what an earlier version left that the chain no longer reads. Bytecode and `.DS_Store` are never copied nor reported.

Before writing or removing anything, it refuses (exit 2, nothing written) when a file it would overwrite or remove is modified, staged or untracked, unless `--force`. Outside a git work tree that guard does not apply.

## Consequences

A file added under `skills/surface-*` or `agents/surface-*.md` ships without registration. A host that wants its own skill or agent uses another prefix. `.claude/surface.json` is the developer's to write, and the chain runs without it. A property test asserts that the host's `surface.json` and `surface.md` survive an install byte for byte, whatever they hold.
