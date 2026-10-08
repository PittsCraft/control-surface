# 0025. End to end tests on a toy project, in a container, on demand

Status: accepted
Date: 2026-09-29

## Context

The chain is made of prompts. The unit tests hold the state script, the installer and the prompts' contract, but none shows that a session driven by those prompts does what the README promises: resuming a killed session, stopping on a modified blueprint, handing back at the ceiling. Only a real session shows it, and it costs money and minutes, and its path varies from run to run. A first harness allowed only the commands a developer's rules would grant; the runs then failed on the commands agents chose to explore with, not on the chain.

## Decision

`tests/e2e/toy/toy.py` builds a toy project from scratch per scenario: a git repository with a small module, its tests and a gate command, a bare local remote, the chain installed from the clone under test, and a plan folder driven to a chosen state through the installed state script, so the journal is real and every guard applies. A session is `claude --print` in that project, with user settings and MCP servers left out, and its stream of events kept as the log.

Sessions run with `--permission-mode bypassPermissions`, so a scenario fails on the chain's behavior and not on an agent's exploration. Since bypassing is not safe on a developer's machine, they run in the container of `tests/e2e/Dockerfile`, as a user that is not root, with the clone mounted read-only and the token passed from the environment. `toy.py` refuses to start a session outside the container.

The scenarios are pytest tests, outside the default run: `scripts/gate.sh e2e` runs them on demand, never in CI. Those that need the developer's answers give them written, one session per answer: every question of the chain carries a recommendation, so a reply that takes it answers a question that changes from run to run, and no model plays the developer there, which is what the evaluations do ([ADR 0036](0036-evaluations-on-real-sessions.md)).

## Consequences

A run costs dollars and tens of minutes: it runs before a release or after a change of the prompts, not on every commit. Assertions stay on what the README promises, not on the path a model takes, and a failure is read in the logs before it is blamed on the chain. The runs need Docker and a token. They no longer show whether an agent's commands are ones a developer's rules can read; the prompts' rule of plain commands from the root, read in review, covers that.
