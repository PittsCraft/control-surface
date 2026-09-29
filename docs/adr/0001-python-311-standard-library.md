# 0001. Runtime floor Python 3.11, standard library only

Status: accepted
Date: 2026-09-29

## Context

The state script and the installer run inside host projects that the chain knows nothing about. They cannot ask a host to install dependencies, and hosts run whatever Python their machine or CI image provides.

## Decision

The script and the installer require Python 3.11 and import nothing but the standard library. 3.11 brings `StrEnum`, `typing.assert_never`, `Self` and `datetime.UTC`, and it runs on every current CI image. The launcher of the script refuses an older interpreter (the macOS system Python 3.9, for instance) with a clear one-line message.

## Consequences

No install step for a host beyond copying files. Newer language features than 3.11 are off limits in the runtime. The floor is enforced by `requires-python`, by `.python-version`, by the ruff and type checker targets, and by running the tests on 3.11 in the gates. Development tools may depend on anything, since they never ship.
