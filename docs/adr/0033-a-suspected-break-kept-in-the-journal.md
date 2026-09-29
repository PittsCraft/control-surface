# 0033. A suspected break is kept in the journal until a reviewer judges it

Status: accepted
Date: 2026-09-29

## Context

When an executor suspects a contract break during a slice, it stops, leaves its work uncommitted and returns its reason. Until a reviewer's verdict is recorded, that reason lived only in the conversation of `/surface-execute`. A session that died in between left the plan in `executing` with uncommitted work, and a relaunch launched a fresh executor on the same slice: it could suspect the same break again, one more agent spent, or carry on past it without anyone having judged it.

Two places could keep the reason: a file of the plan folder, which the dispatcher would have to notice among the uncommitted ones, or the journal, which the state script replays and which `show --json` already turns into fields a dispatcher branches on (ADR 0014).

## Decision

The journal keeps it, as a twentieth event: `break-suspected`, with `slice` and `why`, the reason on one line. The executor records it before it returns, the way it records `slice-done`, and commits nothing: the line rides in the commit that records the reviewer's verdict.

The fold keeps the last suspicion no one has judged. `suspicion-dismissed` and `plan-change-proposed` judge it, and an `amendment-received` drops it, since the plan is drawn again. A block and a resumption keep it. While it waits, the journal-only guards refuse `slice-done`, `plan-amended` and another `break-suspected`, with the refusal code `suspicion`, so nothing carries the slice on unjudged, at record or at replay; a judgment of another slice is refused with the same code. `break-suspected` is not a pass of the loop, so the ceiling never refuses to keep a reason.

`show --json` gives the suspicion as `pending_suspicion`, `{slice, why}` or null, and names the next step: a reviewer judges it. The loop of `/surface-execute` has a row for it, after the ceiling and before `executing`, which launches the reviewer with the reason read from that field. The same row serves the turn that saw the executor return and a session launched after it.

Journals written before this change stay valid. They never hold `break-suspected`, so no suspicion is ever pending in them, and a judgment with no pending suspicion is still accepted. The line keeps `"v": 1`: its form is unchanged, and an event added to the closed list is not a new form (ADR 0012). The JSON answer keeps `"v": 1` too, since a field is added (ADR 0014).

## Consequences

A killed session resumes on the reviewer, with the reason, and a fresh executor cannot record past an unjudged suspicion. The reason is one line, as the other reasons of the journal: the reviewer reads the uncommitted work for the rest. A script older than this change refuses a journal holding `break-suspected`, as it would any event it does not know: the script and the prompts are installed together, so a project meets that only when a branch reads a journal written with a newer install.
