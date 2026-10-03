#!/usr/bin/env python3
"""Run the evaluations of the chain: `evals/README.md` says how, and `--help` lists the commands."""

import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parent
# The harness, the toy project of the end to end tests it builds on, and the state script's
# package, whose readers of a plan folder it reuses.
for folder in (
    EVALS,
    EVALS.parent / "tests" / "e2e" / "toy",
    EVALS.parent / "skills" / "surface-status" / "scripts",
):
    sys.path.insert(0, str(folder))

from surface_evals.cli import main  # noqa: E402 (the path comes first)

if __name__ == "__main__":
    sys.exit(main())
