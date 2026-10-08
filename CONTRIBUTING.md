# Contributing

For work on the chain itself. To use it in a project, see the [README](README.md) and the [guide](docs/guide.md).

## Setup

Python 3.11 minimum, [uv](https://docs.astral.sh/uv/) for the environment.
`uv sync --frozen` sets it up, `uv run pre-commit install` installs the local hooks
(the checks of the gates, and the commit message rules).

## Gates

Every gate of this repository, one command, the one CI runs:

```sh
scripts/gate.sh
```

It runs formatting, lint, strict typing, then the tests on Python 3.11 and on the newest Python. `scripts/gate.sh e2e` runs the end to end tests on a toy project, in a Docker container: real sessions, billed, on demand only and never in CI. Their operating guide, interactive scenarios included, is `tests/e2e/README.md`. `scripts/gate.sh evals` runs the evaluations of the chain, in the same container and billed too: whether it meets its goals and what it is like to work with, after a change of the prompts. Their guide is `evals/README.md`.

The conformity check in a CI shaped checkout is `tests/ci/`: part of the gates, and a job of its own in `ci.yml`.

## Layout

- `skills/`: the skills of the chain, installed as `.claude/skills/surface-*/`. `surface-status/scripts/` holds the state script, standard library only, with no network access.
- `install.py`: the installer and the drift check.
- `evals/`: the evaluations on real sessions: a synthetic host, a corpus of needs, the rubric of the judge, the harness, and the reports of the campaigns kept.
- `ARCHITECTURE.md`: the architecture as it is now, with a codemap and the invariants. Read it first.
- `docs/adr/`: the few decisions whose history matters.
- `docs/guide.md`: the manual for the developer who uses the chain; the README keeps to the idea.
- `docs/images/`: the README's diagrams, each an Excalidraw source (`.excalidraw`) and its two exports, light and dark, made from Excalidraw with the background off.

## Installer

From a clone, `python3 install.py <host>` installs or updates, `python3 install.py --check <host>` writes nothing and exits 1 on drift. Piped from the public repository, it downloads the archive of `--ref` (`main` by default) and installs from it as from a clone; `--archive-url` overrides where the archive comes from.

Ownership is by namespace: the installer owns `.claude/skills/surface-*/` and `.claude/agents/surface-*.md`. It overwrites them, removes those the source no longer has, and refuses when one of them holds uncommitted work or is not tracked by git, unless `--force` is given. It never touches anything else, and creates no settings file.

## State script

`surface-status` is the only writer of each plan's `journal.jsonl`. State is derived from the journal, never stored, and the script refuses any transition its table does not allow, and any event whose guard fails. Its subcommands (`show`, `resolve`, `record`, `gate`, `abandon`, `commits`, `pr-body`, `check`) serve the developer and the skills, and a host may call `check` from its CI; `--json` is for the skills.

## Text rules

No em dash in any file of the repository, checked by the gates. Commit messages carry no em dash and no attribution to Claude, checked by the `commit-msg` hook. What the hook accepts and refuses is in `scripts/check_commit_msg.py`.

## Decisions

A pull request that changes the architecture updates `ARCHITECTURE.md` in the same pull request. An ADR in `docs/adr/` is rare: only for a decision that is hard to reverse, is structural or bears on a key quality, was chosen against credible alternatives, or is one a reader is likely to "fix". It is short (context, decision, consequences) and has no amendment log: a replaced record is marked superseded, and `ARCHITECTURE.md` changes with it.
