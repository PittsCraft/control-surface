"""Evaluations of the chain on real sessions (ADR 0036).

Does the chain meet its goals, and is it good to work with: measured after a change of the
prompts, on demand, with no human in the loop. `evals/README.md` is the operating guide.
"""

from pathlib import Path

EVALS = Path(__file__).resolve().parents[1]
CLONE = EVALS.parent
HOST = EVALS / "host"
CASES = EVALS / "cases"
JUDGE = EVALS / "judge"
REPORTS = EVALS / "reports"
