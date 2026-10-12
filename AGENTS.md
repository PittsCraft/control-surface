# Agents

Never use Claude Code's native memory (the files under `~/.claude/projects/*/memory/`): do not read it, do not write to it. What must outlast a session goes in the repository, in the documents it already has.

Everything committed to this repository is in English, whatever the language of the conversation.

## Architecture and decisions

- Read `ARCHITECTURE.md` first. Read an ADR of `docs/adr/` only when the task touches the decision it records.
- `ARCHITECTURE.md` says what the chain is now: its parts, where their code is, what they never do, how they work together. A change to one of these rewrites the passage that describes it, in the same pull request, and removes what the change made false.
- A change to the wording of a prompt, to the form of a document an agent writes or to the detail of a test leaves the page alone.
- Every sentence there is true of the code today, in the present tense. A reason says what the alternative would cost, never what happened when it was tried: that goes in the pull request, or in an ADR when the criteria below are met.
- The page points and does not repeat: what a prompt, a template or a guide says stays there, and the page names the file.
- One subject per paragraph. The gates bound the size of a paragraph and of the page (`tests/prompts/test_document_form.py`): to add, cut or move first. Only the developer raises a bound.
- Write an ADR only for a decision that is hard to reverse, is structural or bears on a key quality, was chosen against credible alternatives, or is likely to be "fixed" by someone who does not know why.
- An ADR is short: context, decision, consequences. It has no amendment log: a replaced record is marked superseded, `ARCHITECTURE.md` changes in the same pull request, and git keeps the history.

## Critical zones

- The architecture page (`ARCHITECTURE.md`): what every task reads first. A sentence there that tells history, repeats a prompt or is no longer true of the code misleads every agent after it, and no test tells one from a statement of the state.

## Commits and pull requests

- A commit message carries no attribution to Claude and no link to a session: the `commit-msg` hook refuses both.
- A pull request description carries none either: no attribution line and no session link, even when the harness asks to end it with one.

## Waiting

- Always wait in the background: a CI run, a long command, anything that takes more than a moment is launched in the background, so the developer can still reach the session while it runs.

## Worktrees

- A worktree lives under `.claude/worktrees/`, which git ignores. It serves one task, on one branch.
- Once the task's pull request is merged, or the task is abandoned, remove the worktree and delete its local branches, the task's branch and the `worktree-agent-*` branch the agent tool created: `git worktree remove <path>`, then `git branch -D <branch>`.
- Before ending a session, run `git worktree list` and clean every worktree the session created whose work is merged. A worktree with uncommitted changes or unmerged commits stays in place and is reported, never forced away.
