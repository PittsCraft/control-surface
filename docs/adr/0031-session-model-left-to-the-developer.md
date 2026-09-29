# 0031. The session's model and effort are the developer's; the chain pins only the agents' models

Status: accepted
Date: 2026-09-29

## Context

ADR 0021 had `/surface-execute` pin Sonnet in its frontmatter and report, when the loop stopped, that a later turn ran on another model. ADR 0024 had `surface-plan` pin Opus and the effort `high`, and warn at load and at each later turn when the session left them. The documentation of skills (https://code.claude.com/docs/en/skills, read on 2026-09-29) applies a skill's `model` and `effort` to the turn that invokes it only, by design. Every later turn runs on the developer's session: a background agent that hands back opens one, and so does each answer of the developer in the interview of `/surface-plan`, whatever `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` says.

The warnings cannot be reliable: a model does not know for sure which model it runs on, nor where a turn ended. A headless run ended with "The last step ran in a later turn on Opus 5.5 rather than Sonnet" while its stream shows both Agent calls in the foreground: the Opus lines were the reviewer's.

The agents are not affected. The dispatcher passes the `model` of `surface.json` on each Agent call, which wins over every other setting (ADR 0021), and the runs show each agent on its model.

## Decision

The session's model and effort are the developer's choice, as its permissions are (ADRs 0028, 0030). The chain pins what it controls, the agents' models, set in `surface.json` and passed on each Agent call, and says what it recommends for the session.

- `surface-plan` has no `model` and no `effort` in its frontmatter, and no warning at load or at a later turn.
- `/surface-execute` has no `model` in its frontmatter, reports no model switch when the loop stops, and no longer advises `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`. It still asks for the foreground when the Agent tool offers it; nothing depends on it.
- The README recommends Opus with the effort `high` for `/surface-plan`, and says that `/surface-execute` dispatches soundly on any model while the agents run on the models of `surface.json`.

This amends ADR 0021, whose dispatcher pinned Sonnet and reported a later turn on another model, and ADR 0024, whose command pinned Opus and `high` and warned when a turn left them. The models of the agents, their `effort` in the frontmatter, and the test that holds the definitions equal to the defaults of `settings.py` stay as ADR 0021 set them.

## Consequences

No prompt claims to pin or check the session's model or effort. A developer who plans on a weaker model gets a weaker interview and plan, and the README says what to choose. The dispatch costs what the developer's session costs: sound on Opus as on Sonnet, as ADR 0021 found. Tests hold that the commands carry no `model` nor `effort`, and the README's recommendation.
