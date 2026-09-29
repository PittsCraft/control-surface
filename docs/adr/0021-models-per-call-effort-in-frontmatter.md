# 0021. Models passed on each call, effort in the frontmatter

Status: accepted
Date: 2026-09-29

## Context

The model of each agent role is a setting of the host, in `surface.json`, so a project changes it without editing an installed file. The Claude Code documentation of subagents (checked on 2026-09-29) resolves a subagent's model in this order: the `model` parameter of the Agent call, then the `model` of the definition's frontmatter, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the session's model. It documents `effort` as a frontmatter field only (`low`, `medium`, `high`, `xhigh`, `max`, depending on the model); the Agent call takes no effort.

## Decision

The dispatching command reads the model of each role from `surface-status show --json` (`settings.models`) and passes it as the `model` of every Agent call. Each definition still carries a `model`, the alias the settings default to (`opus` for the extractor, the checker and the reviewer, `sonnet` for the executor), so a definition launched without one runs on the documented model. A test holds the frontmatter equal to the defaults of `settings.py`. Models are aliases, never full identifiers, to follow releases.

`effort: high` sits in the frontmatter of the three judgment roles. The executor has no `effort` and runs at the session's.

## Consequences

A host sets a model in `surface.json` and sees no drift. A host that wants another effort edits an installed definition, and the drift check reports it: effort per host has no other way in. If the Agent call gains an effort parameter, `surface.json` can grow an `effort` key and this record is revised.
