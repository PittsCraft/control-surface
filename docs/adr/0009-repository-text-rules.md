# 0009. Repository text rules as tests and hooks

Status: accepted
Date: 2026-09-29

## Context

The maintainer's writing rules (no em dash in the repository, no mention of Claude in commit messages) are easy to break by habit and were checked by memory.

## Decision

No tracked text file may contain an em dash: `tests/prompts/test_repo_text.py` checks tracked files and untracked files that are not ignored, and runs in the gates. A `commit-msg` hook (`scripts/check_commit_msg.py`, wired in `.pre-commit-config.yaml`) refuses a message with an em dash or any attribution to Claude, in any letter case: an attribution trailer (`Co-Authored-By:` and the like) naming Claude or Anthropic, a "generated with" line, a link to Claude or Anthropic, or Claude as a standalone word of the prose. Paths and identifiers that merely contain the name (`.claude/`, `CLAUDE.md`, `${CLAUDE_PROJECT_DIR}`) and inline code in backticks are accepted, since the chain installs into `.claude/` and its commits must be able to say so. Comment lines and everything below git's scissors line are ignored, as git drops them.

A first version refused the word anywhere, which would have refused any commit citing `.claude/`, the directory the chain installs into.

## Consequences

The rules are checked by a machine on every gate run and on every commit of a clone that ran `uv run pre-commit install`. The hook is local, so CI cannot check commit messages; the text rule still runs in CI.
