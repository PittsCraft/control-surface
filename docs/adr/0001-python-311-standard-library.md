# 0001. Runtime floor Python 3.11, standard library only, no network

Status: accepted
Date: 2026-09-29

## Context

The state script and the installer run inside host projects the chain knows nothing about. They cannot ask a host to install dependencies, and hosts run whatever Python their machine or CI image provides. The chain also promises that the state script reaches no network, and a promise in a README does not hold that.

## Decision

The state script and the installer need Python 3.11 and import only the standard library. 3.11 brings `StrEnum`, `assert_never`, `Self` and `datetime.UTC`, and every current CI image has it. The launcher of the script and the installer refuse an older Python in one line instead of failing on syntax.

The state script has no network access, held three ways: a test fails on any import outside `sys.stdlib_module_names`; ruff's `TID251` bans `socket`, `urllib`, `http` and `ssl` everywhere but `install.py`, the tests and the repository scripts; and every test runs with sockets blocked.

## Consequences

A host installs nothing but the copied files, and needs `sh`, `git` and `python3` 3.11. Language features newer than 3.11 are off limits in the runtime; the gates run the tests on 3.11. Development tools may depend on anything, since they never ship. Adding a dependency or a network call means changing the ban list, the import test and this record, on purpose.
