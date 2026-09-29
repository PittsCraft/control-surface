# Agents

Never use Claude Code's native memory (the files under `~/.claude/projects/*/memory/`): do not read it, do not write to it. What must outlast a session goes in the repository, in the documents it already has.

## Architecture and decisions

- Read `ARCHITECTURE.md` first. Read an ADR of `docs/adr/` only when the task touches the decision it records.
- A change to the architecture updates `ARCHITECTURE.md` in the same pull request: the parts, the codemap, an invariant, a crosscutting concern, with its reason in one sentence.
- Write an ADR only for a decision that is hard to reverse, is structural or bears on a key quality, was chosen against credible alternatives, or is likely to be "fixed" by someone who does not know why. Everything else goes in `ARCHITECTURE.md`.
- An ADR is short: context, decision, consequences. It has no amendment log: a replaced record is marked superseded, `ARCHITECTURE.md` changes in the same pull request, and git keeps the history.
