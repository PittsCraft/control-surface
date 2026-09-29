import socket

import pytest


def test_sockets_are_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.getaddrinfo("example.com", 80)
    with socket.socket() as sock, pytest.raises(RuntimeError, match="network access is blocked"):
        sock.connect(("127.0.0.1", 9))
