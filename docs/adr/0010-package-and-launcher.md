# 0010. The script is a package plus a launcher; it has no network access

Status: accepted
Date: 2026-09-29

## Context

The state script is called by skills, by agents and by a host's CI, from a directory that is not its own. It has to be readable and testable as several typed modules, and yet a host must be able to run it with no install step: the installer copies files and nothing more. The chain also promises that the script has neither dependency nor network access, and a promise in a README does not hold that.

## Decision

The code is the package `surface_status/`, under `.claude/skills/surface-status/scripts/` in a host. Beside it sits `surface-status`, a launcher written in POSIX shell: it checks that `python3` on the PATH is 3.11 or newer, says so in one line on standard error and exits 2 if it is not (or is missing), then runs `python3 -B -m surface_status.cli` with the package directory on `PYTHONPATH`. `-B` keeps bytecode out of the host's `.claude/`. The launcher checks the version before it touches anything else, so a Python 3.9 never reaches a syntax it does not know.

A skill, an agent and a host CI call `.claude/skills/surface-status/scripts/surface-status` from the root of the repository: one file path, nothing to install. (The skills first called it through `${CLAUDE_PROJECT_DIR}`; ADR 0028 moved them to the relative path, which a permission rule of the project can name.)

The absence of a network is held three ways. A test walks every import of the package and fails on any module outside `sys.stdlib_module_names` (`pyproject.toml` declares no runtime dependency either). Ruff's `TID251` bans `socket`, `urllib`, `http` and `ssl` everywhere except `install.py`, the tests and the repository scripts, so the package cannot import them even from the standard library. And `tests/conftest.py` blocks sockets for every test, so a command that tried to connect would fail its test.

## Consequences

A host needs `sh` and `python3` 3.11 or newer, which the README lists. Windows without a POSIX shell is not a target, like the rest of the chain, which runs git and shell commands. The one line of the launcher is tested with a fake `python3` that fails the version check. Adding a dependency or a network call means changing the ban list, the import test and this record, on purpose.
