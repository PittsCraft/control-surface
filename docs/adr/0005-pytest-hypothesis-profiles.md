# 0005. pytest with hypothesis, two profiles

Status: accepted
Date: 2026-09-29

## Context

The guarantees of the state machine are properties over all event sequences, not examples. Local runs must stay fast, CI can afford more.

## Decision

Tests use pytest and hypothesis. `tests/conftest.py` registers two profiles, selected by `HYPOTHESIS_PROFILE`: `dev` (default, 50 examples) and `ci` (500 examples, example database off, `print_blob` on so a CI failure can be replayed locally). Every test runs with sockets blocked.

## Consequences

Wider search in CI without slowing the local loop. A failing CI property prints a blob that reproduces it. Tests that need the network cannot exist by accident.
