# 0012. The script computes every derived field; the journal has one canonical form

Status: accepted
Date: 2026-09-29

## Context

An agent that records an event can get a derived value wrong: a hash read before the file changed, a slice list copied from memory, a report number that is already taken. The journal is append only, so a wrong line stays. Replaying a journal must also always give the same state (ADR 0011), which is easier to guarantee when the text of a line is fixed and not merely its meaning.

## Decision

Callers pass judgments only (counts, reasons, results, the paths of reports they wrote). The script derives the rest: `at` from the clock, the hashes from the files, `slices` from the `<!-- slice:N -->` markers of `plan.md`, report and run numbers from what exists in the plan folder.

`record` (`record.py`) is the only code that appends. Its order is fixed and every step but the last only reads: replay the journal, `admit` the event with the settings it needs (ceiling, gate command, current overview hash), apply the guards that need the plan folder (`disk_guards`), then append. The guards of the plan folder are pure functions over a `DiskFacts` value the caller reads, so `guards.py` still opens no file (ADR 0011): every cited file must be a regular file inside the plan folder (a name that leaves it, or a link that resolves outside it, counts as missing; `overview.md` and `plan.md` count when the event carries their hash, and `gates-run` cites `gates/run-NN.txt`); a hash carried by the event must be the current hash of its file; the slices carried by `plan-drafted` and `plan-amended` must be those of `plan.md`, and a plan whose markers cannot be read cannot be drafted.

A line is `v`, `at`, `event`, then the own fields in the order the dataclass declares them, as JSON with the default separators and no escaping of non ASCII text. The codec accepts that form only. Decoding refuses a version other than 1, an unknown or missing field, a wrong type (a boolean is not a number), a duplicate key, `NaN`, a hash that is not `sha256:` and 64 lower case hexadecimal digits, a date that is not `YYYY-MM-DDTHH:MM:SSZ` and real, and any line that does not re-encode to the very same text. Encoding refuses what decoding would refuse, so a line the reader cannot take is never written. The journal is read as UTF-8, split on `\n` only, and must end with a newline; a journal that does not is refused for reading and for appending, which is what a torn write leaves. The writer opens the file for appending, writes one line and flushes it to disk. It takes no lock: a single script writes, and git arbitrates between machines.

## Consequences

A hand edit that reformats a line, reorders its keys or escapes a character makes replay fail at that line, with its number. That is intended: the journal is edited by the script or by no one. A caller cannot record a stale hash or a wrong slice list; it can only be refused, with a code the CLI branches on (`file-missing`, `hash-stale`, `slices-stale`). Adding a field to an event needs a rule in the codec, and the codec raises `NotImplementedError` on a type it does not know, which a test reaches through the strategy that covers every event.
