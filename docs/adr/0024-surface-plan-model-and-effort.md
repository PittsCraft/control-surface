# 0024. surface-plan pins Opus and high effort, and warns when a later turn leaves them

Status: accepted, amended by ADR 0031
Date: 2026-09-29

## Context

The interview and the plan are meant to be written on Opus with the effort `high`, in the session the developer launches. Whether the model a skill pins holds from one turn to the next had to be checked. The documentation read on 2026-09-29 settles it:

- https://code.claude.com/docs/en/skills: the `model` of a skill "applies for the rest of the current turn"; the session model resumes at the next prompt. The `effort` field "overrides the session effort level". The rendered skill enters the conversation once, and "Claude Code does not re-read the skill file on later turns"; substitutions such as `${CLAUDE_EFFORT}` are made at that rendering.
- https://code.claude.com/docs/en/model-config: the session returns to its previous effort level when the skill completes; `/model` and `/effort` change the session's.

An interview spans several turns, so the pinned model and effort hold only for its first one. And `${CLAUDE_EFFORT}` gives the effort at load, not at a later turn.

## Decision

`surface-plan` sets `model: opus` and `effort: high` in its frontmatter. Its body tells the session to check, from its second turn on, the model its environment names, and to open its answer with a one-line warning and `/model opus` when it is not an Opus model. The effort is read once, at load, from `${CLAUDE_EFFORT}`, with a one-line warning and `/effort high` when it is below `high`. Since later turns cannot read the effort, the session tells the developer once, when the interview goes past the first turn, that `/model opus` and `/effort high` keep the target for the session.

## Consequences

The first turn, where the exploration happens, runs on the target. Later turns run on the developer's session settings, and the developer is told how to hold the target. A frontmatter test holds `model` and `effort`, and a body test holds the warning. Comparing the effort at every resumed turn was the first intent; the documentation makes it impossible.
