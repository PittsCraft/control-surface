# 0016. The plans of a branch, from git objects

Status: accepted
Date: 2026-09-29

## Context

Nothing records which plans belong to a branch: git computes it. Listing plans from the main branch must also see the plans of unmerged branches without touching the working tree, since the developer may have uncommitted work.

## Decision

The plans of the current branch are the folders of the plans directory that hold a journal in the work tree and that the merge base does not have. The work tree is read, not `HEAD`, so a plan opened and not yet committed counts, and its journal is the one `record` just wrote. A folder the merge base already holds is never the branch's plan, terminal or not: this is what keeps the plan folders kept on main after earlier merges out of every answer, and a merge of main into the branch (which moves the merge base) leaves them out too.

The plans of another branch are the folders its commit has and its own merge base with main does not. Their journal is read with `git cat-file blob <ref>:<path>` and replayed in memory; no checkout, no fetch, nothing written. A branch that exists locally and on `origin` is scanned once, as the local one. A journal that cannot be read on another branch is reported in the answer instead of stopping it, since that branch is not the developer's current work; the same journal on the current branch is exit 2.

`commits <plan>` lists the commits `HEAD` has and the main branch has not, without merges, oldest first. A commit belongs to the plan whose `journal.jsonl` it touches (to several if it touches several), and to no plan if it touches none: the developer's commits. The answer gives `commits` (of the plan) and `unowned`, with `base`, the merge base with main. The diff to review is `git diff <base> HEAD`: a merge of main into the branch moves `base` forward, so it brings nothing foreign into the diff and none of main's commits into the lists. Renames should be turned off when reading that diff (`--no-renames`), so that a file moved on main is not read as a move on the branch.

`pr-body` gives the description of the branch: a table of every plan of the branch (terminal ones too) with its state and links to `overview.md` and `plan.md`. The links point at the branch on GitHub when `origin` is a GitHub address, and are paths from the repository root otherwise. A branch with no plan has no description (exit 1).

## Consequences

The script reads git and never writes it. Every git command runs with `git -C <project root>` and a timeout, so a project that is a folder inside a repository works. A CI checkout needs the full history (`fetch-depth: 0`), and says so when it does not have it.
