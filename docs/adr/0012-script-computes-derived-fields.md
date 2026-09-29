# 0012. The script computes every derived field; the journal has one canonical form

Status: accepted
Date: 2026-09-29

## Context

An agent that records an event can get a derived value wrong: a hash read before the file changed, a slice list copied from memory, a report number already taken. The journal is append only, so a wrong line stays. Replay must also always give the same state ([ADR 0011](0011-pure-fold-and-two-families-of-guards.md)), which is easier when the text of a line is fixed and not merely its meaning.

## Decision

Callers pass judgments only: counts, reasons, results, the paths of the reports they wrote. The script derives the rest: the date, the hashes, the slices from the `<!-- slice:N -->` markers of `plan.md`, the gates from its `gates` block, the report and run numbers. A derived value passed on the command line is a usage error.

`record.py` is the only code that appends. It replays, admits the event, checks the plan folder (every cited file is a regular file inside it, a carried hash is the current one, carried slices and gates are those of `plan.md`), then appends one line and flushes it. It takes no lock: one script writes, and git arbitrates between machines.

A line is `v`, `at`, `event`, then the event's fields in declared order, as JSON with the default separators. The codec accepts that form only, and refuses any line that does not re-encode to the very same text. Encoding refuses what decoding would refuse. A journal that does not end with a newline, what a torn write leaves, is refused for reading and appending.

## Consequences

A hand edit that reformats a line fails replay at that line: the journal is edited by the script or by no one. A caller cannot record a stale hash or slice list, only be refused with a code (`file-missing`, `hash-stale`, `slices-stale`, `gate-list`). A new field needs a rule in the codec. An event added to the closed list is not a new form and keeps `"v": 1`.
