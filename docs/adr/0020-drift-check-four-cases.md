# 0020. Drift check with four cases

Status: accepted
Date: 2026-09-29

## Context

A host that installs the chain by copy must be able to tell, without writing anything, whether its copy still matches the source, and why it does not: a file missing, a file edited in place, a file the source dropped, or an installation never committed.

## Decision

`install.py --check <host>` writes nothing and prints one line per difference, then exits 1, or 0 with "no drift":

- `missing : <path>`: the source has the file, the host does not.
- `drift : <path>`: the host file differs from the source in content or in its executable bit.
- `orphan : <path>`: an owned file the source no longer has.
- `uncommitted : <path>`: in a git work tree, an installed file that git shows as modified, staged, untracked or ignored. An installation is finished once committed, and a file covered by `.gitignore` stays out of history for good.

Usage errors and download failures exit 2. Outside a git work tree the `uncommitted` case is skipped.

## Consequences

A fresh install reports `uncommitted` until it is committed. The output is the same from a clone and from the one-line form, which a test compares.
