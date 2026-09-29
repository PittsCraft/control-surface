# 0018. Installer in Python

Status: accepted
Date: 2026-09-29

## Context

A shell script, `install.sh`, was the first idea. The installer copies files, compares them, asks git about them and, run from the public repository, downloads and unpacks an archive.

## Decision

The installer is `install.py`, standard library only, at the root of the repository. It is checked by the same gates as the rest (ruff, mypy, pyright) and tested with pytest on temporary git repositories, run as a subprocess the way a user runs it. It is written to parse on older interpreters, so that `python3` 3.9 prints "needs Python 3.11" instead of a syntax error.

## Consequences

No shellcheck or bats on top of the toolchain. A host needs `python3` 3.11 and `git`, plus `curl` for the one-line form. The archive is unpacked by hand (regular files and directories only, paths checked to stay inside the target) because `tarfile` extraction filters do not exist in every 3.11 patch release.
