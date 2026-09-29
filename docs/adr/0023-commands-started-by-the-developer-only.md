# 0023. Commands started by the developer only

Status: accepted
Date: 2026-09-29

## Context

The three commands of the chain act on the repository: they record events, commit, push and write the description of a pull request. The Claude Code documentation of skills (https://code.claude.com/docs/en/skills, read on 2026-09-29) lets a skill be loaded by Claude on its own when its description seems relevant, unless its frontmatter sets `disable-model-invocation: true`. With that field, only the developer invokes the skill by typing its name; its description stays out of the context; it is not preloaded into subagents, and a scheduled task cannot fire it.

## Decision

Every command of the chain sets `disable-model-invocation: true`. The four agents are not skills and are launched by the commands only, with the Agent tool.

## Consequences

Claude never starts planning, approving or executing because a conversation looks ready for it: an approval by launch (`/surface-execute`) stays an act of the developer. A frontmatter test holds the field on each command. The developer types `/surface-plan`, `/surface-execute` or `/surface-status`; the descriptions still show in the `/` menu.
