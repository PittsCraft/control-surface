# 0028. The permissions of an unattended loop live in the developer's settings

Status: accepted, amended by ADRs 0030 and 0032
Date: 2026-09-29

## Context

The end to end runs (ADR 0025) stopped again and again on a permission prompt nobody answered: an agent that meets a denial stops, and the loop with it. The commands grant the state script, git and `gh` in their `allowed-tools`, but the Claude Code documentation of skills (https://code.claude.com/docs/en/skills, read on 2026-09-29) says that grant holds "during the turn that invokes this skill" and "clears when you send your next message". The agents run under the session's rules, and the runs showed that an agent often hands back asynchronously, so the loop goes on in a later turn, without the grant: `gh pr edit` was denied in every such run, and the pull request description was never refreshed.

A rule of the project settings is a plain text match on the command (https://code.claude.com/docs/en/permissions, same date): a rule cannot follow `${CLAUDE_PROJECT_DIR}`, which the skills substituted with an absolute path, one per machine. The same page says the read-only commands, `git log` or `grep` among them, need no rule, and that a `cd` followed by git asks for an approval.

## Decision

The README gives, in the developer's path before the agents work, a "Permissions" section: a block of settings ready to paste into `.claude/settings.json` or `.claude/settings.local.json`, with the state script, the writing forms of git the loop uses, `gh pr view`, `gh pr edit` and `gh pr ready`, and the gate command as an example to replace; then why the rules belong there. A test holds the block as valid settings that cover every rule of the commands' `allowed-tools`.

Every prompt calls the state script by its path from the root of the repository, `.claude/skills/surface-status/scripts/surface-status`, never through `${CLAUDE_PROJECT_DIR}`, so that one rule names it on every machine. Commands run from the root, never after a `cd`. `surface-plan` keeps the absolute path for the one call it injects at load, and grants both forms.

The installer never writes the Claude Code settings of the host: it ends by pointing at the section. `/surface-execute` checks nothing at launch: the rules in force come from several settings files, managed ones included, and from the command line, and a session cannot read them, so any check would guess.

The end to end harness allows the rules of that block, read from the README, and not more for git: a denial in a run is a finding on the chain or on the section.

## Consequences

A developer grants the loop once per project, in files they own and can share. A new command in a prompt that no rule of the block covers shows up as a denial in the end to end runs, and the block grows with it. The absolute path of ADR 0010 remains only in the injected call of `surface-plan`.
