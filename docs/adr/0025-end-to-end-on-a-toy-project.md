# 0025. End to end tests on a toy project, headless, on demand

Status: accepted
Date: 2026-09-29

## Context

The chain is made of prompts: the skills and the agents. The unit tests hold the state script, the installer and the text of the prompts, but none of them shows that a session driven by those prompts does what the README promises: resuming where a killed session stopped, stopping on a modified overview, handing back at the ceiling, not raising a refused break again. Only a real session shows it, and a real session costs money and minutes, and its path varies from one run to the next.

## Decision

A toy project, built from scratch for each scenario by `tests/e2e/toy/toy.py`: a git repository holding a small Python module, its tests and a gate command (`python3 -m unittest`), with a bare local repository as its remote. The chain is installed from the clone under test with `install.py`. A plan folder is then driven to a chosen state by writing the files the chain would have written and recording each event through the installed state script, so the journal is a real one and every guard applies to the way there. A scenario starts from such a state rather than from the specs, so that it spends its budget on the behavior it checks.

A session is `claude --print` in the toy project, with its stream of JSON events kept as the log:

- user settings are left out (`--setting-sources project,local`), since their hooks, permissions and model would change the run, and MCP servers too;
- permissions are those a developer who followed the README would grant: file edits (`--permission-mode acceptEdits`), and on the command line the rules of the README's Permissions section, read from it, with the toy's gate command, the branch commands of `/surface-plan` and the usual reading commands of the shell (`cat`, `ls`, `grep`, `mkdir` and the like). Nothing is bypassed. A project's own settings grant nothing in a folder Claude Code was never told to trust, so the list is given on the command line.

The scenarios a single session can play are pytest tests in `tests/e2e/`: the nominal path to `conform`, a session killed in a slice then relaunched, an overview modified after its approval, the ceiling. They assert on files, the journal and the state the script derives, and on the final message only where the stop itself is the behavior. `tests/e2e` is outside the default test run, and `scripts/gate.sh e2e` runs it on demand, never in CI.

The scenarios that need the developer's answers, the interview, an amendment, the refusal of a plan change, are played by hand from the same states, one session per answer (`--resume` with the session id, or a fresh session to test resumption), following `tests/e2e/README.md`.

## Consequences

A run of the automated scenarios costs dollars and tens of minutes; it is run before a release or after a change of the prompts, not on every commit. A failure is read in the logs before it is blamed on the chain: a model can take another valid path, and the assertions stay on what the README promises, not on the path. A draft pull request cannot be opened on a local remote: that step shows the chain's behavior without `gh` or a GitHub remote. Nobody approves a command in a headless session, and an agent stops at its first denial: the runs therefore also check that the agents issue commands a developer's permission rules can read, which is what an unattended loop needs in any project.
