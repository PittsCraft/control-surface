# The container of the end to end tests (ADR 0030). Its sessions bypass permissions, which is safe
# here and not on the developer's machine. `scripts/gate.sh e2e` builds and runs it; the manual
# scenarios of tests/e2e/README.md use it too. No credential is written in the image: the token
# comes from the environment of `docker run`.
FROM node:22-bookworm-slim

# The developer's user id, so that the logs written in the mounted folder are theirs.
ARG UID=1000

# Python 3.11, the runtime floor of the chain, and git.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates git python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global @anthropic-ai/claude-code \
    && npm cache clean --force

# pytest runs the scenarios; the conftest of tests/ loads the hypothesis profiles.
RUN python3 -m venv /opt/e2e \
    && /opt/e2e/bin/pip install --no-cache-dir "pytest>=8.2" "hypothesis>=6.100"

# Claude Code refuses to bypass permissions as root.
RUN userdel --remove node \
    && useradd --create-home --uid "$UID" tester

# SURFACE_E2E_CONTAINER lets toy.py start a session; the clone is mounted read-only at /clone.
ENV PATH=/opt/e2e/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    SURFACE_E2E_CONTAINER=1
USER tester
WORKDIR /clone
