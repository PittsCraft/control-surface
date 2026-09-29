# Architecture decisions

Each decision has its context, the decision itself and its consequences.

| # | Decision |
|---|---|
| 0001 | [Runtime floor Python 3.11, standard library only](0001-python-311-standard-library.md) |
| 0002 | [uv for the dev toolchain, lockfile committed](0002-uv-dev-toolchain.md) |
| 0003 | [ruff for format and lint, select ALL](0003-ruff-select-all.md) |
| 0004 | [mypy strict and pyright strict, both gating](0004-mypy-and-pyright-strict.md) |
| 0005 | [pytest with hypothesis, two profiles](0005-pytest-hypothesis-profiles.md) |
| 0006 | [Coverage measured and printed, never a failing threshold](0006-coverage-without-threshold.md) |
| 0007 | [One entry point for gates: scripts/gate.sh](0007-single-gate-entry-point.md) |
| 0008 | [CI triggers, pinned actions, read-only permissions](0008-ci-triggers-and-hardening.md) |
| 0009 | [Repository text rules as tests and hooks](0009-repository-text-rules.md) |
| 0010 | [The script is a package plus a launcher; it has no network access](0010-package-and-launcher.md) |
| 0011 | [State is a pure fold; guards split by what they need](0011-pure-fold-and-two-families-of-guards.md) |
| 0012 | [The script computes every derived field; the journal has one canonical form](0012-script-computes-derived-fields.md) |
| 0013 | [Content hash: SHA-256 with CRLF read as LF](0013-content-hash-normalizes-crlf.md) |
| 0014 | [Exit codes, and a versioned JSON answer](0014-exit-codes-and-json-shape.md) |
| 0015 | [Main branch detection, and the plan that `resolve` designates](0015-main-branch-detection-and-resolve.md) |
| 0016 | [The plans of a branch, from git objects](0016-plans-of-a-branch-from-git-objects.md) |
| 0017 | [The gate runner refuses to start at the ceiling](0017-gate-runner-refuses-to-start-at-the-ceiling.md) |
| 0018 | [Installer in Python](0018-installer-in-python.md) |
| 0019 | [Ownership by namespace](0019-ownership-by-namespace.md) |
| 0020 | [Drift check with four cases](0020-drift-check-four-cases.md) |
| 0021 | [Models passed on each call, effort in the frontmatter](0021-models-per-call-effort-in-frontmatter.md) |
| 0022 | [Each agent role is a leaf](0022-agents-are-leaves.md) |
| 0023 | [Commands started by the developer only](0023-commands-started-by-the-developer-only.md) |
| 0024 | [surface-plan pins Opus and high effort, and warns when a later turn leaves them](0024-surface-plan-model-and-effort.md) |
| 0025 | [End to end tests on a toy project, headless, on demand](0025-end-to-end-on-a-toy-project.md) |
| 0026 | [Plan documents follow the language of the specs](0026-plan-documents-in-the-language-of-the-specs.md) |
| 0027 | [One-line install from the public repository](0027-one-line-install.md) |
| 0028 | [The permissions of an unattended loop live in the developer's settings](0028-permissions-of-an-unattended-loop.md) |
| 0029 | [The conformity check, proved in a checkout shaped like a CI's](0029-conformity-check-proved-in-a-ci-shaped-checkout.md) |
| 0030 | [Exploration is left to the permission mode; end to end runs bypass it in a container](0030-exploration-left-to-the-permission-mode.md) |
| 0031 | [The session's model and effort are the developer's; the chain pins only the agents' models](0031-session-model-left-to-the-developer.md) |
