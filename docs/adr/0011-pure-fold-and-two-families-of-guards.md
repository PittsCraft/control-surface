# 0011. State is a pure fold; guards split by what they need

Status: accepted
Date: 2026-09-29

## Context

The state of a plan is derived from its journal alone, never stored, and a journal must always give the same state. Some guards need facts outside the journal: the ceiling of passes from `surface.json`, whether the approved plan names gates, the current hash of `blueprint.md`. A guard that read them during replay would make an old journal invalid the day a setting changes, and would make replay depend on the disk.

## Decision

`events.py`, `machine.py` and `guards.py` open no file. The transition table is data. `admit(state, event, context)` checks the table, then the guards, and returns an acceptance or a refusal with a code. `fold(events)` takes the events alone and raises on an illegal line, so a hand edited journal cannot replay silently.

Guards fall in two families:

- Journal-only guards need the state and the event, and run at replay and at record.
- Record-time guards need a `RecordContext` of plain values the caller read beforehand (the ceiling, whether the approved plan names gates, the current blueprint hash), and run at record only. They cover the frozen blueprint, the ceiling of autonomous passes and the gate results.

The pass counters and "the gate result since the last change" are facts of the state, reset by each act of the developer. `conformant` needs a clean review made since the last change of the work.

## Consequences

A journal stays valid whatever the settings become. The recording code computes the context itself, which also keeps a caller from declaring a hash. Guards that need the disk live beside these, over plain values too ([ADR 0012](0012-script-computes-derived-fields.md)). Tests check that replay reads no file: by signature, by the imports of the three modules, and by a replay with file access forbidden.
