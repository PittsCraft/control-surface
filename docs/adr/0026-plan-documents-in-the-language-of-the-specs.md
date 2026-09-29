# 0026. Plan documents follow the language of the specs

Status: accepted
Date: 2026-09-29

## Context

A plan folder holds documents the chain writes for the developer, and their language has to be chosen. The developer writes `specs.md` and reads `overview.md` to approve it; the agents read every file whatever its language. The chain itself is written in English.

## Decision

Every document the chain writes in a plan folder (`exploration.md`, `interview.md`, `plan.md`, `overview.md`, the reports) is written in the language of `specs.md`. The templates of `surface-plan` are in English and say so: their headings are translated, their structure kept. What a script reads never depends on the language: slice markers are `<!-- slice:N -->` lines, and the journal is JSON written by the script. The command speaks to the developer in the language they write in.

## Consequences

A developer approves an overview in their own language, and the answers they give are recorded in their own words. The agent definitions and the templates already carry the rule ("Write in the language of `specs.md`"), and a test holds it on each template. A repository whose conventions impose one language for its documents states it in `.claude/surface.md` or writes its specs in that language.
