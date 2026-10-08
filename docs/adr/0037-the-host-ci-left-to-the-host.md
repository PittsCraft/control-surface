# 0037. The host's CI left to the host

Status: accepted
Date: 2026-10-08

## Context

The chain had grown three holds on the CI of the host. Before the first push of a branch, `/surface-plan` read what triggers the CI, warned the developer and waited for their agreement when a push or a new pull request would start a run. The guide gave a GitHub Actions workflow that ran the conformity check once the pull request was marked ready, with the depth its checkout needs. And the hand back at conformity said that marking the pull request ready "triggers your CI".

Each bound the chain to what every host does its own way: a CI system, its triggers, its checkout. The warning had to read the configuration of any CI. The workflow was one host's shape, had never run on a hosted repository, and named an action to keep current. The sentence at conformity was false in a host with no CI. And a check prescribed at the moment a pull request is marked ready decided when a finished plan may leave the plans in progress: its folder had to stay on the branch, readable, until the merge.

## Decision

The chain acts on nothing of the host's CI.

`/surface-plan` still reads the CI configuration for what it says of the project, the commands that check it and their order, as it reads a manifest. It reads no trigger, warns of nothing and asks nothing before a push. No prompt says what a push or a ready mark starts. The chain still never marks a pull request ready: what the host runs then is the developer's to start.

`surface-status check --require conformant` stays, as a command the developer runs before merging. The guide says that a CI can call it, with its exit codes and the full history it needs, and gives no workflow. The script goes on answering in a detached or shallow checkout, which `tests/ci` holds.

## Consequences

In a host whose CI runs on every push, the first push of a plan starts a run nobody announced: that is a configuration of its CI, not a thing the chain guesses. Whether the conformity check runs in a CI, and at which moment, is the developer's call, and so is the moment a finished plan leaves the plans in progress. The end to end tests keep no project with a CI, and nothing of the chain is left to exercise on a hosted CI.
