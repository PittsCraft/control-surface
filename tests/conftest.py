"""Shared test setup: hypothesis profiles, and no network for any test."""

import os
import socket
from typing import NoReturn

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile("dev", max_examples=50, deadline=None)
settings.register_profile(
    "ci",
    max_examples=500,
    deadline=None,
    database=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


def _refuse(*_args: object, **_kwargs: object) -> NoReturn:
    message = "network access is blocked in tests"
    raise RuntimeError(message)


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
