# 0007. One entry point for gates: scripts/gate.sh

Status: accepted
Date: 2026-09-29

## Context

Gates that differ between the local machine and CI make a green CI a coincidence, and a red one a surprise.

## Decision

`scripts/gate.sh` runs every gate: ruff format check, ruff check, mypy, pyright, then pytest on Python 3.11 and on the newest Python through `uv run --isolated --python` (the newest is `3.14`, overridable with `GATE_NEWEST_PYTHON`). CI runs this very script. `scripts/gate.sh e2e` is the opt-in run of the end to end tests and is never part of the default run.

## Consequences

The local run is the working check and CI only confirms it. The script stops at the first failing gate.
