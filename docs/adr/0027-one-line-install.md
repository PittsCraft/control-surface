# 0027. One-line install from the public repository

Status: accepted
Date: 2026-09-29

## Context

Installing the chain should be one command, from the public repository, needing nothing but `python3`, `curl` and `git`.

## Decision

```sh
curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py | python3 -
```

Fed from standard input, `install.py` has no sources next to it. It targets the current directory (or the given host), downloads the archive of a version with the standard library (`https://github.com/PittsCraft/control-surface/archive/<ref>.tar.gz`), unpacks it in a temporary directory, and installs from it as from a clone. `--check` works the same way. The version is `--ref`, `main` by default, a branch, a tag or a commit, validated against a strict pattern. `--archive-url` replaces the source of the archive (`{ref}` stands for the version, schemes `https` and `file` only), which is how the tests serve a local archive without any socket. `--ref` or `--archive-url` given from a clone makes it download too.

An archive that is unreadable or holds no `templates/surface.json` and `templates/surface.md` is refused before anything is written or removed, so a wrong archive can never empty a host of its chain.

## Consequences

`main` is the default version, so a re-run updates to the tip of `main`; a tag or a commit pins.
