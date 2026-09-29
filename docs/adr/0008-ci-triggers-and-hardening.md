# 0008. CI triggers, pinned actions, read-only permissions

Status: accepted
Date: 2026-09-29

## Context

The repository is public, so Actions minutes are free: a rule limiting CI triggers, which makes sense for a repository billed by the minute, would buy nothing here. Gates still run locally before every push.

## Decision

`.github/workflows/ci.yml` triggers on `pull_request` (types `opened`, `synchronize`, `reopened`, `ready_for_review`, draft pull requests skipped until ready) and on `push` to `main`. Actions are pinned by commit SHA with the version in a comment, permissions are `contents: read`, and a concurrency group cancels superseded runs.

## Consequences

A pull request is checked on every push to it, and main is checked after every merge. Bumping an action is a deliberate SHA change.
