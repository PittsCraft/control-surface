# 0033. A suspected break is kept in the journal until a reviewer judges it

Status: accepted
Date: 2026-09-29

## Context

When an executor suspects a contract break during a slice, it stops, leaves its work uncommitted and returns its reason. That reason lived only in the conversation of `/surface-execute` until a reviewer's verdict was recorded. A session that died in between left the plan in `executing`, and a relaunch started a fresh executor on the same slice: it could suspect the same break again, or carry on past it with no one having judged it.

Two places could keep the reason: a file of the plan folder, which the dispatcher would have to notice among the uncommitted ones, or the journal, which the script replays and `show --json` already turns into fields a dispatcher branches on.

## Decision

The journal keeps it, as the event `break-suspected` with `slice` and a one-line `why`. The executor records it before it returns, and commits nothing: the line rides in the commit of the reviewer's verdict.

The fold keeps the last unjudged suspicion. `suspicion-dismissed` and `plan-change-proposed` judge it, `amendment-received` drops it, a block and a resumption keep it. While it waits, the journal-only guards refuse `slice-done`, `plan-amended` and another `break-suspected` with the code `suspicion`, at record and at replay. It is not a pass, so the ceiling never refuses to keep a reason. `show --json` gives it as `pending_suspicion`, and the loop of `/surface-execute` has a row that launches the reviewer on it.

## Consequences

A killed session resumes on the reviewer, with the reason, and a fresh executor cannot record past an unjudged suspicion. Journals written before stay valid: they hold no suspicion. A script older than this change refuses a journal holding `break-suspected`; the script and the prompts are installed together, so a project meets that only when reading a branch written with a newer install.
