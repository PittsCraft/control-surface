#!/usr/bin/env bash
# Every gate, one command. CI runs this very script.
#   scripts/gate.sh        static checks, then tests on 3.11 and on the newest Python
#   scripts/gate.sh e2e    the end to end tests: billed, on demand only, never in CI (ADR 0025);
#                          the arguments after `e2e` go to pytest, like `-k nominal`
# GATE_NEWEST_PYTHON overrides the interpreter of the second test run.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n== %s ==\n' "$*"; }

if [ "${1:-}" = "e2e" ]; then
  if [ ! -d tests/e2e ]; then
    echo "gate: no end to end tests yet (tests/e2e does not exist)" >&2
    exit 1
  fi
  if ! command -v claude >/dev/null 2>&1; then
    echo "gate: the end to end tests need the claude CLI on the PATH, logged in" >&2
    exit 1
  fi
  shift
  step "e2e (billed: every scenario runs real sessions)"
  uv run pytest -o addopts= -ra tests/e2e "$@"
  exit 0
fi

step "ruff format"
uv run ruff format --check .
step "ruff check"
uv run ruff check .
step "mypy"
uv run mypy
step "pyright"
uv run pyright
step "claude plugin validate agents"
if command -v claude >/dev/null 2>&1; then
  claude plugin validate agents --strict
else
  echo "gate: the claude CLI is not on the PATH, validation skipped (the frontmatter tests still run)"
fi
step "claude plugin validate skills"
if command -v claude >/dev/null 2>&1; then
  claude plugin validate skills --strict
else
  echo "gate: the claude CLI is not on the PATH, validation skipped (the frontmatter tests still run)"
fi
step "pytest, Python 3.11 (with coverage report)"
uv run --isolated --python 3.11 pytest --cov --cov-report=term-missing
step "pytest, newest Python (${GATE_NEWEST_PYTHON:-3.14})"
uv run --isolated --python "${GATE_NEWEST_PYTHON:-3.14}" pytest
echo
echo "gate: all green"
