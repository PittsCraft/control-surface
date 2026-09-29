# 0002. uv for the dev toolchain, lockfile committed

Status: accepted
Date: 2026-09-29

## Context

The repository needs interpreters (3.11 and the newest) and a handful of development tools, reproducibly, locally and in CI.

## Decision

uv manages interpreters and dependencies. Development tools are declared in the `dev` dependency group of `pyproject.toml`, `uv.lock` is committed, the project is not a package (`package = false`), and CI runs `uv sync --frozen` so a stale lock fails instead of being silently updated.

## Consequences

One tool for the whole toolchain, already the maintainer's habit. Contributors need uv. Upgrading a tool is a visible lock diff.
