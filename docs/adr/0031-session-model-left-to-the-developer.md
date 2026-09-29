# 0031. The session's model and effort are the developer's; the chain pins only the agents' models

Status: accepted
Date: 2026-09-29

## Context

The chain first pinned models in the commands: `/surface-plan` set Opus and the effort `high` and warned when a later turn left them; `/surface-execute` set Sonnet and reported when a later turn ran on another model. The Claude Code documentation of skills (read on 2026-09-29) applies a skill's `model` and `effort` to the turn that invokes it only. Every later turn runs on the developer's session: each answer in the interview, and each background agent that hands back. The warnings could not be reliable either: a model does not know for sure which model it runs on, nor where a turn ended, and a headless run reported a model switch that its log disproved.

The agents are not affected. A subagent's model is, in order, the `model` of the Agent call, of its definition, then of the environment, then of the session. The Agent call takes no effort; the definition's frontmatter does.

## Decision

The commands carry no `model` and no `effort`, and no prompt claims to pin or check the session's. The README recommends Opus with the effort `high` for `/surface-plan`.

The dispatching command reads each role's model from `show --json` (`settings.models`, from `surface.json` or its defaults) and passes it on every Agent call. Each definition also carries that default alias, so an agent launched without one runs on it; a test holds the definitions equal to the defaults of `settings.py`. Models are aliases, never full identifiers. `effort: high` sits in the frontmatter of the three judgment roles; the executor runs at the session's.

## Consequences

The agents, which do the work, run on the models of `surface.json` whatever the turn. The dispatch runs on the developer's session and is sound on Opus as on Sonnet; only its cost differs. A developer who plans on a weaker model gets a weaker plan, and the README says what to choose. Effort per host means editing an installed definition, which the drift check reports.
