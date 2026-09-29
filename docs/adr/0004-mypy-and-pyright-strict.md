# 0004. mypy strict and pyright strict, both gating

Status: accepted
Date: 2026-09-29

## Context

mypy and pyright disagree on inference in useful places. Pyright is what most editors run, mypy is the long standing reference.

## Decision

Both run in strict mode over the same code, both gate. mypy is configured with `strict = true`, pyright with `typeCheckingMode = "strict"`, both targeting Python 3.11.

## Consequences

Two checks of a small codebase are cheap, and a disagreement points at code that is ambiguous for a reader. A construct that passes one and fails the other must be rewritten, or ignored with a justified comment.
