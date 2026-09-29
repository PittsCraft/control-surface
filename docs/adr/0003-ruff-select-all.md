# 0003. ruff for format and lint, select ALL

Status: accepted
Date: 2026-09-29

## Context

A short hand picked rule list silently misses every rule added later.

## Decision

ruff formats and lints with `select = ["ALL"]` and a short ignore list. Each ignored rule carries a comment saying why, either in the global list or in a per-file entry. Docstrings are not mandatory (`D1`), since names and types carry the contract.

## Consequences

New rules arrive on upgrade and must be fixed or ignored with a stated reason. Formatter conflicts (`COM812`, `ISC001`) and the docstring style pairs (`D203`, `D213`) are ignored because they cannot both hold.
