# 0030. Exploration is left to the permission mode; end to end runs bypass it in a container

Status: accepted, amended by ADR 0032
Date: 2026-09-29

## Context

ADR 0028 put the rules an unattended loop needs in the developer's settings, and the end to end harness of ADR 0025 allowed those rules, the toy's gate command, the branch commands of `/surface-plan` and a few reading commands of the shell, and nothing else: a denial in a run was a finding on the chain or on the README's Permissions section. The runs kept finding denials, and each was fixed in the prompts after the run: `git ls-tree`, a `cd` then git, `git -C`, `find ... -exec`, `python3 -c` probes, `echo $?`. Most came from an agent exploring the code, not from a step a prompt imposes.

What an agent runs to explore depends on the model and on the host project: its tooling, its language, its scripts. Closing each role's list of commands is a race the chain cannot win. Claude Code already answers this with its permission modes: auto mode decides on a command without asking, `bypassPermissions` allows every one.

## Decision

The Permissions block of the README covers what the prompts themselves require: the state script, the writing forms of git, `gh pr`, the gate. It does not try to list what an agent may run to explore. The section is reduced to a warning and the block: the loop stops at every command the developer's rules or mode do not allow, so run it in auto mode, or allow at least the block. Claude Code users know the problem: the why of ADR 0028, a grant that clears at the next turn and no check at launch, leaves the README and stays in that record. A denial in an end to end run is no longer a finding on the block.

The prompts keep asking for plain commands run from the root, no `cd` then git, no `git -C`, since those serve a developer on the default mode too. No test tries to close each role's list of commands.

The end to end sessions run with `--permission-mode bypassPermissions`, so that a scenario fails on the chain's behavior and not on an agent's exploration. Bypassing on the developer's machine is not safe, since a command can reach outside the toy folder, so the scenarios run in a container, `tests/e2e/Dockerfile`: Python, git, the `claude` CLI and pytest, under a user that is not root, since Claude Code refuses to bypass permissions as root. The clone under test is mounted read-only. The toy projects, their bare remotes and the logs of the sessions live in the container, under a folder mounted from the host so that the logs outlive it. The session logs in with `CLAUDE_CODE_OAUTH_TOKEN`, from `claude setup-token`, or `ANTHROPIC_API_KEY`, passed from the environment and never written in the image: the login of a macOS host lives in its keychain, which a container cannot read. `toy.py` refuses to start a session outside the container, which the image marks with an environment variable, so nobody bypasses permissions on their machine by accident. `scripts/gate.sh e2e` builds the image and runs pytest in it. User settings and MCP servers stay left out (`--setting-sources project,local`, `--strict-mcp-config`).

This amends ADR 0028, whose harness allowed the rules of the block and no more, and the permissions of the sessions in ADR 0025, which bypassed nothing.

## Consequences

The end to end runs need Docker and a token, and the manual scenarios run in the same container. They no longer show whether the agents issue commands a developer's rules can read: a prompt that imposes a new command must add it to the block, which the review reads for, and the test that holds the block against the commands' `allowed-tools` stays. A developer on the default mode may still be asked to approve a command an agent chose to explore with; that is the call of their permission mode, not of the chain.
