# 0029. The conformity check, proved in a checkout shaped like a CI's

Status: accepted, amended by ADR 0032
Date: 2026-09-29

## Context

The conformity check is meant to run in the host project's CI, where the checkout is not a developer's clone: HEAD is detached, there is no local branch, and the remote branches are all there is. Tests on a developer's repository do not prove it works there, and a proof that only the CI runs cannot be run before a push.

## Decision

`tests/ci/` installs the chain from this checkout into a toy project, in clone mode, builds a conform plan and an in-progress plan with the state script, and pushes them to a local bare repository. It then leaves a repository the way `actions/checkout` does (`git init`, a fetch of the remote branches, a detached checkout, no local branch) and runs `check --require conform`: exit 0 on the conform plan, 1 on the in-progress plan. A checkout at depth 1 is recorded as it behaves: exit 2, naming `fetch-depth: 0`, because the merge base with `origin/main` cannot be found (ADRs 0015 and 0016). The README snippet for the host's CI prescribes `fetch-depth: 0`, and a test holds it.

The scenario is plain pytest, so `scripts/gate.sh` runs it locally, and the `conformity` job of `ci.yml` runs the same tests on their own, on the same triggers as `gates`.

## Consequences

The proof runs before a push and in the CI, from one source. It does not run against GitHub's own runner image: a change in what `actions/checkout` leaves would show only in the job's real run, which is why that job exists.
