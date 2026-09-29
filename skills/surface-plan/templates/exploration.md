# Exploration: <feature>

What the exploration of the repository established, so that a relaunched session never explores again. Written in the language of `specs.md`: translate the headings. What is not listed under "Read" was not read.

## Repository rules

- Domain: the business concepts the feature touches, in the words of the repository's domain document.
- Architecture: the style, the boundaries that must hold, and what enforces them.
- Generated artifacts: what is derived from a source of truth and never edited by hand.
- Gates: every check a change must pass, in the order they run, and the command that runs them all if there is one.
- Conventions: branches, commits, pull requests, reviews.
- Decisions: where they are recorded, and in what form.
- CI: what triggers it (a push, a pull request opened, marked ready for review, a merge).

If the repository states none of this, say so, and the minimum the plan will hold to.

## What the feature touches

- The domain objects it extends, and the precedent to copy: the last thing added the same way, or "none".
- Every layer on the path, from the outermost interface down to persistence.
- What the change forces to regenerate.
- The tests around the precedent, whose shape the plan reuses.

## Project declarations

What `.claude/surface.md` declares: critical zones, conventions. "None" when the file is missing or empty.

## Read

The files read, by path.
