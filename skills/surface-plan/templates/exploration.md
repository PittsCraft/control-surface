# Exploration: <feature>

What the exploration of the repository established, so that a relaunched session never explores again. Written in the language it names below, in its repository rules, the language of every document of the plan folder: translate the headings. What is not listed under "Read" was not read.

## Repository rules

- Domain: the business concepts the feature touches, in the words of the repository's domain document.
- Architecture: the style, the boundaries that must hold, and what enforces them.
- Generated artifacts: what is derived from a source of truth and never edited by hand.
- Gates: every check a change must pass, in the order they run, the command of each and where it was found, and the command that runs them all if there is one. Then the gates of the plan: the commands its `gates` block will hold, in their order, or that none was found and the interview asks.
- Conventions: branches, commits, pull requests, reviews.
- Decisions: where they are recorded, and in what form.
- Language: the language of the plan documents, and where it was found: a language the agent instructions declare, else that of the repository's documentation, else that of the specs. Every document of the plan folder is written in it, and every agent reads it here.

If the repository states none of this, say so, and the minimum the plan will hold to.

## What the feature touches

As far as the interview needs, so that no question is asked that the code answers. The path through the code, layer by layer, is read by the agent that drafts the plan, and is told there.

- The domain objects it extends, and the precedent to copy: the last thing added the same way, or "none".
- What the code already settles of the need, and what it leaves open.

## Project declarations

What the repository's agent instructions (`AGENTS.md`, `CLAUDE.md`) declare: critical zones, conventions. "None" when they declare nothing.

## Read

The files read, by path.
