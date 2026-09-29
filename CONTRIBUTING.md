# Contributing

For work on the chain itself. To use it in a project, see the [README](README.md).

## Setup

Python 3.11 minimum, [uv](https://docs.astral.sh/uv/) for the environment.
`uv sync --frozen` sets it up, `uv run pre-commit install` installs the local hooks
(the checks of the gates, and the commit message rules).

## Gates

Every gate of this repository, one command, the one CI runs:

```sh
scripts/gate.sh
```

It runs formatting, lint, strict typing, then the tests on Python 3.11 and on the newest Python. `scripts/gate.sh e2e` runs the end to end tests on a toy project: real sessions, billed, on demand only and never in CI. Their operating guide, interactive scenarios included, is `tests/e2e/README.md`.

The conformity check in a CI shaped checkout is `tests/ci/`: part of the gates, and a job of its own in `ci.yml`.

## Layout

- `skills/`: the skills of the chain, installed as `.claude/skills/surface-*/`. `surface-status/scripts/` holds the state script, standard library only, with no network access.
- `templates/`: the two settings files, `surface.json` and `surface.md`, created in the host project when missing.
- `install.py`: the installer and the drift check.
- `docs/adr/`: the architecture decisions.

## Installer

From a clone, `python3 install.py <host>` installs or updates, `python3 install.py --check <host>` writes nothing and exits 1 on drift. Piped from the public repository, it downloads the archive of `--ref` (`main` by default) and installs from it as from a clone; `--archive-url` overrides where the archive comes from.

Ownership is by namespace: the installer owns `.claude/skills/surface-*/` and `.claude/agents/surface-*.md`. It overwrites them, removes those the source no longer has, and refuses when one of them holds uncommitted work or is not tracked by git, unless `--force` is given. It never touches anything else, and creates `.claude/surface.json` and `.claude/surface.md` only when they are missing.

## State script

`surface-status` is the only writer of each plan's `journal.jsonl`. State is derived from the journal, never stored, and the script refuses any transition its table does not allow, and any event whose guard fails. Its subcommands (`show`, `resolve`, `record`, `abandon`, `commits`, `pr-body`, `check`) serve the developer, the skills and the host project's CI; `--json` is for the skills.

## Text rules

No em dash in any file of the repository, checked by the gates. Commit messages carry no em dash and no attribution to Claude, checked by the `commit-msg` hook. See `docs/adr/0009-repository-text-rules.md`.

## Decisions

Record each architecture decision in `docs/adr/`, numbered, with its context, the decision and its consequences.
