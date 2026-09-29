# 0011. State is a pure fold; guards split by what they need

Status: accepted
Date: 2026-09-29

## Context

The state of a plan is derived from its journal alone, never stored, and replaying a journal must read no other file, so that a journal always gives the same state. Some guards, though, need facts that live outside the journal: the ceiling of passes and the gate command come from `surface.json`, the current hash of `overview.md` from the plan folder. A guard that reads those facts during replay would make an old journal invalid the day a setting changes, and would make replay depend on the disk.

## Decision

The core is three modules of the standard library, none of which opens a file:

- `events.py` holds the closed list of 20 events (the twentieth, `break-suspected`, by ADR 0033) as frozen dataclasses. `v` and `at` belong to the journal line and are added and stripped by the codec, so the core never sees a date. An attribute `x_` stands for the journal key `x` (`pass`, `slice`).
- `machine.py` holds the ten states, the transition table as data (event, departure, arrival; the departure `None` is the journal that does not exist yet) and `apply`, the pure step from one state to the next. An arrival that depends on the journal is a named `Rule`, resolved with `match` and `assert_never`.
- `guards.py` holds the guards, `admit(state, event, context)` and `fold(events)`. `admit` checks the table first, then the guards, and returns `Accepted(state)` or `Refusal(code, reason)`.

Guards fall in two families:

- Journal-only guards need the state and the event: the cross-check covers the drafted hashes, the approved overview is the drafted one, a slice is declared and not done, a fix keeps the list of slices, a break comes with a proposal, a suspected break is judged before its slice goes on, conformity follows a clean review of the approved overview. They run at replay and at record.
- Record-time guards need a `RecordContext` of plain values the caller read beforehand: the ceiling, whether a gate command is declared, the current overview hash. They run at record only. They cover the frozen overview (`slice-done`, `plan-amended`, `fix-done`, `conform`), the ceiling of autonomous passes, and the gate guards of `review-done` and `fix-done`, which are lifted when no gate command is declared.

`fold` takes nothing but the events, returns `None` for an empty journal and raises `InvalidJournalError` (line, event, refusal) when a line is illegal, so a hand edited journal cannot replay silently. That replay reads no other file is tested by signature, by the imports of the three modules, and by running a replay with file access forbidden.

Two choices are worth recording:

- The pass counters and the "gate result since the last change" are facts of the state, reset by each act of the developer (planning: `interview-closed`, `amendment-received`, `plan-change-accepted`, `resumed`; execution: `plan-approved`, `plan-change-refused`, `resumed`). A green gate run stands until a `slice-done` or a `review-done`, as the guard words it, or until the plan goes back to drafting.
- `conform` needs a clean review made since the last change of the work. The last review is forgotten by `slice-done`, `fix-done`, `amendment-received`, `plan-approved` and `plan-change-accepted`, otherwise a clean review followed by a failed gate run and a fix would still license conformity. The rule itself is unchanged: the last review must count nothing to fix.

Not enforced, because no guarantee of the chain needs it: that `plan-change-accepted` and `plan-change-refused` cite the pending proposal, that the numbers carried by `review-done` and `fix-done` follow each other, and that a slice list holds no duplicate (the marker parser of `plan_folder.py` refuses those).

## Consequences

A journal stays valid whatever the settings become. The recording code has to compute the context values itself and hand them in, which also keeps a caller from declaring a hash. File existence guards, which need the disk, belong to that code and sit beside these ones (ADR 0012). A refusal carries a code, so the CLI and the tests branch on it and not on prose.
