# 0014. Exit codes, and a versioned JSON answer

Status: accepted
Date: 2026-09-29

## Context

`surface-status` is read by three audiences: a developer, skills that branch on what it says, and CI jobs that branch on whether it failed. Prose changes and is translated; a code and a field do not.

## Decision

Exit codes: 0 when an event is accepted or a check passes, 1 when an event is refused or a check fails (a verdict the caller can act on), 2 when the call itself is wrong (unknown plan, missing or malformed field, a setting file that does not parse) or a journal cannot be read or replayed. A check that meets an unreadable journal exits 2 even if another plan failed too, since nothing it says about that plan can be trusted.

With `--json`, standard output holds one JSON object, indented by two spaces, with `"v": 1` first. Without it, an answer goes to standard output and a refusal or an error to standard error. The shapes, pinned by the golden files of `tests/fixtures/cli/`:

- list (no subcommand): `plans`, a list of `{name, state, hand}`; a plan whose journal cannot be read has `state` and `hand` null and an `error`;
- `show`: `plan`, `state`, `hand`, `next_step`, `slices {declared, done, remaining}`, `passes {planning, execution, ceiling}`, `pending_proposal`, `last_event`, `settings` (the effective ones, in the shape of `surface.json`);
- `record` and `abandon`, accepted: `ok` true, `plan`, `event`, `at`, `state`; refused: `ok` false, `plan`, `event`, `refused {code, reason}`, where `code` is one of the refusal codes of `guards.RefusalCode`;
- `check`: `ok`, `require` (null or `conform`), `plans`, a list of `{name, state, ok, problems}`, each problem `{code, message}`, the codes being `in-progress`, `abandoned-after-approval`, `overview-changed`, `overview-missing` and `journal-unreadable`;
- any call that exits 2: `ok` false and `error`.

A field is added without a new version, a field is renamed or removed only with `"v": 2`. `record` takes judgments only (counts, reasons, the paths of the reports the caller wrote), so a derived value passed on the command line is a usage error (ADR 0012).

## Consequences

A skill reads the code first and the fields second, and a CI job needs nothing but the code. The refusal of an agent and the failure of a check share code 1, which is right for both: the work is not done, and the next step is to fix the cause and try again. `gates-run` cannot be recorded through `record`: an exit code is a fact, and the gate runner (ADR 0017) is the only writer of it.
