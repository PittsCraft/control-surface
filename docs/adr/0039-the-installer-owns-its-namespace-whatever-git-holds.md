# 0039. The installer owns its namespace, whatever git holds of it

Status: accepted
Date: 2026-10-16
Supersedes: [0019](0019-ownership-by-namespace.md)

## Context

The installer must update what it installed, remove what the source dropped, and leave every other file of the host alone, without a manifest that someone has to keep in step with the sources. Earlier versions also created `.claude/surface.json` and `.claude/surface.md` in the host.

Record 0019 added a guard: the installer refused to overwrite or remove a file of its namespace that git showed as modified, staged, untracked or ignored, unless `--force`, and the check reported such a file as `uncommitted`.

A host that keeps `.claude/` out of git holds every installed file untracked. There each update was refused and each check failed, while the files were byte for byte what an earlier install wrote. A guard that fires on every update is passed with `--force` by habit, and then protects nothing.

## Decision

The installer owns `.claude/skills/surface-*/` and `.claude/agents/surface-*.md`, and nothing else is written, replaced or removed. There it overwrites and removes whatever git holds of the files, and it never runs git.

It creates no settings file and never reads or writes `.claude/settings.json`; it only names what an earlier version left that the chain no longer reads. Bytecode and `.DS_Store` are never copied nor reported. The check reports `missing`, `drift` and `orphan`, and nothing of git.

## Consequences

An edit made in the host to a file of the namespace is lost at the next install, and git keeps it only when it was committed. A host that wants its own skill or agent, or its own copy of one, uses another prefix. A file added under `skills/surface-*` or `agents/surface-*.md` ships without registration.

`.claude/surface.json` is the developer's to write, and the chain runs without it. A property test asserts that the host's `surface.json` and `surface.md` survive an install byte for byte, whatever they hold.

`install.py` is Python, not shell, so it shares the gates and the tests; it parses on old interpreters to say it needs 3.11 instead of failing on syntax. Piped from the public repository, it downloads the archive of `--ref` (`main` by default), unpacks it by hand, and installs as from a clone. It has no `--force`, since nothing is left to force.
