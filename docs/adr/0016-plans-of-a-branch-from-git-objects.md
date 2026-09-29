# 0016. The plans of a branch, from git objects

Status: accepted
Date: 2026-09-29

## Context

An agent never guesses a plan: it needs the plan of the branch it is on, and the conformity check of a pull request needs every plan of the branch. Nothing records which plans belong to a branch, and a registry would have to be kept in step by hand. Listing from the main branch must also see the plans of unmerged branches without touching the working tree, where the developer may have uncommitted work.

## Decision

Git computes it. The plans of the current branch are the plan folders that hold a journal in the work tree and that the merge base with the main branch does not have. A folder the merge base holds is never the branch's plan, which keeps plans merged earlier out of every answer. The plans of another branch are the folders its commit adds against its own merge base, read with `git cat-file` and replayed in memory: no checkout, no fetch. A commit belongs to the plans whose journal it touches, and to none otherwise.

The main branch is `origin/HEAD`, else `main`, `master`, `origin/main`, `origin/master`, the last two for a detached CI checkout. There is no setting: a repository with none of them is a usage error. Outside a git work tree, every plan folder with a journal counts.

## Consequences

The script reads git and never writes it; each git command runs in the project root with a timeout. A CI checkout needs the full history (`fetch-depth: 0`), and the check says so when the merge base cannot be found. A branch may carry several plans.
