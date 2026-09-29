# 0017. The gate runner refuses to start at the ceiling

Status: accepted
Date: 2026-09-29

## Context

An agent can declare a success it has not verified; an exit code is a fact. The script therefore runs the project's gates itself and records the result. A failed run counts as a loop pass, and the guards refuse any pass beyond the ceiling. But the result of a run is unknown before it ends: refusing a failed run afterwards would mean the gates had already run, for up to `gate_timeout_minutes`, for nothing, and a green run recorded at the ceiling would be accepted where its failed twin is not.

## Decision

`gate <plan>` asks the journal before it runs anything. It builds the failed run it would record and submits it to `admit`, with the same context as `record`: a state that takes no `gates-run` (only `reviewing` and `fixing` do) and a ceiling already reached both refuse it, with the refusal codes of `record` (`transition`, `ceiling`), exit code 1, and nothing run, written or appended. A gate run at the ceiling is refused whatever it would have returned: no legitimate path needs one, since `conform` needs none and the developer takes the hand back at the ceiling.

Once the run is allowed:

- the command is `gate_command` through `/bin/sh -c`, at the project root, with no standard input, standard output and error merged into one file;
- it starts in its own session, hence its own process group; when it ends, or when `gate_timeout_minutes` has elapsed, the whole group receives `SIGKILL`. A child the command left running in the background is killed with it, so no run leaves a process behind;
- the report `gates/run-NN.txt` is written first (created exclusively, a run number is never reused) with the command, the result, the exit code (none for a timeout, the signal for a killed command), the duration and the last 200 lines of the output; then `gates-run` is recorded through `record`, so the disk guards apply to it like to any event;
- the result is `pass` for exit code 0, `timeout` when the delay was exceeded, `fail` otherwise. A timeout is a failure.

Exit codes follow ADR 0014: 0 for a green run, 1 for a failed or timed out run and for a refusal, 2 for a wrong call. The JSON answer of a run carries `ok`, `plan`, `ran` (true), `run`, `result`, `exit_code`, `duration_seconds`, `report`, `at` and `state`; a refusal has the shape of a refused `record`.

A project that declares no `gate_command` gets exit code 0 and `ran` false with the reason: nothing runs, nothing is recorded, and the guards that concern `gates-run` are lifted, so a review and a fix are accepted without one.

## Consequences

A failed run is the only event whose acceptance depends on something the script measures, and it is the only one that can cost minutes: asking first spends none on a run the journal would refuse. The caller reads the exit code, then the report the answer names; the output of a failed gate is in the file, not on standard output. Processes that leave their session on purpose (`setsid`, a daemon) escape the group; the runner does not chase them.
