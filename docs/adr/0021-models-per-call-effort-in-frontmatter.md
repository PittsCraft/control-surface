# 0021. Models passed on each call, effort in the frontmatter

Status: accepted, amended by ADRs 0031 and 0032
Date: 2026-09-29

## Context

The model of each agent role is a setting of the host, in `surface.json`, so a project changes it without editing an installed file. The Claude Code documentation of subagents (checked on 2026-09-29) resolves a subagent's model in this order: the `model` parameter of the Agent call, then the `model` of the definition's frontmatter, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the session's model. It documents `effort` as a frontmatter field only (`low`, `medium`, `high`, `xhigh`, `max`, depending on the model); the Agent call takes no effort.

The model a command pins is another matter. The documentation of skills (https://code.claude.com/docs/en/skills, read on 2026-09-29) says the `model` of a skill "applies for the rest of the current turn", and its `allowed-tools` grant "clears when you send your next message". The documentation of subagents (https://code.claude.com/docs/en/sub-agents, same date) says when an agent runs in the background: always in an interactive session, where fork mode is on by default and "Claude can't ask for the foreground"; by default in `claude -p`, and in the foreground "when it needs the result before continuing". A background agent hands back in a later turn. The end to end runs (ADR 0025) saw it: `/surface-execute` launched on Sonnet, its agents returned asynchronously, and the rest of the loop ran on the session's model, Opus, without the command's grants (`gh pr edit` was denied every time). The agents themselves kept their model, passed on each call.

The one setting that keeps a loop in its first turn is the environment variable `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`: with it, "Claude Code runs the subagent in the foreground, in every kind of session and whether or not fork mode is on"; it also turns off every other background task of the session. No setting keeps a skill's model past its turn: `CLAUDE_CODE_SUBAGENT_MODEL` and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` choose the model of the agents, not of the session, and `/model` or the `model` setting change the session's own.

## Decision

The dispatching command reads the model of each role from `surface-status show --json` (`settings.models`) and passes it as the `model` of every Agent call. Each definition still carries a `model`, the alias the settings default to (`opus` for the extractor, the checker and the reviewer, `sonnet` for the executor), so a definition launched without one runs on the documented model. A test holds the frontmatter equal to the defaults of `settings.py`. Models are aliases, never full identifiers, to follow releases.

`effort: high` sits in the frontmatter of the three judgment roles. The executor has no `effort` and runs at the session's.

`/surface-execute` asks for the foreground on each Agent call when the tool offers it, and says in one line, when the loop stops, that a later turn ran on another model, with the variable that avoids it. The README says the same in two sentences, and its Permissions section (ADR 0028) grants in the settings what the command grants for its first turn only.

## Consequences

A host sets a model in `surface.json` and sees no drift. A host that wants another effort edits an installed definition, and the drift check reports it: effort per host has no other way in. If the Agent call gains an effort parameter, `surface.json` can grow an `effort` key and this record is revised.

Without the variable, the turns of the dispatcher after the first run on the developer's session model: the dispatching is sound on Opus as on Sonnet, only its cost differs, and the developer is told. The agents, which do the work, run on the models of `surface.json` whatever the turn.
