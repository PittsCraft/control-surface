# Agents

Never use Claude Code's native memory (the files under `~/.claude/projects/*/memory/`): do not read it, do not write to it. What must outlast a session goes in the repository, in the documents it already has.

Everything committed to this repository is in English, whatever the language of the conversation.

## Architecture and decisions

- Read `ARCHITECTURE.md` first. Read an ADR of `docs/adr/` only when the task touches the decision it records.
- A change to the architecture updates `ARCHITECTURE.md` in the same pull request: the parts, the codemap, an invariant, a crosscutting concern, with its reason in one sentence.
- Write an ADR only for a decision that is hard to reverse, is structural or bears on a key quality, was chosen against credible alternatives, or is likely to be "fixed" by someone who does not know why. Everything else goes in `ARCHITECTURE.md`.
- An ADR is short: context, decision, consequences. It has no amendment log: a replaced record is marked superseded, `ARCHITECTURE.md` changes in the same pull request, and git keeps the history.

## Commits and pull requests

- A commit message carries no attribution to Claude and no link to a session: the `commit-msg` hook refuses both.
- A pull request description carries none either: no attribution line and no session link, even when the harness asks to end it with one.

## Waiting

- Always wait in the background: a CI run, a long command, anything that takes more than a moment is launched in the background, so the developer can still reach the session while it runs.

## Worktrees

- A worktree lives under `.claude/worktrees/`, which git ignores. It serves one task, on one branch.
- Once the task's pull request is merged, or the task is abandoned, remove the worktree and delete its local branches, the task's branch and the `worktree-agent-*` branch the agent tool created: `git worktree remove <path>`, then `git branch -D <branch>`.
- Before ending a session, run `git worktree list` and clean every worktree the session created whose work is merged. A worktree with uncommitted changes or unmerged commits stays in place and is reported, never forced away.
