# 0006. Coverage measured and printed, never a failing threshold

Status: accepted
Date: 2026-09-29

## Context

A coverage threshold turns into a target that gets padded with tests that assert nothing.

## Decision

Coverage is measured with pytest-cov on the 3.11 run of the gates and printed with missing lines. No option makes a run fail on a percentage.

## Consequences

The report is there to read. Untested lines are found by reading it, and by the exhaustive and property tests of the state script, not by a number.
