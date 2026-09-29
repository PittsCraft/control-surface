"""The script has neither dependency nor network access (ADR 0001).

Checked statically here (every import of the package is the standard library or the package
itself, and ruff bans the network modules), and at run time by the socket block of `conftest.py`,
which every test of this folder runs under.
"""

import ast
import socket
import sys
import tomllib
from pathlib import Path

import pytest
from cli_support import Project

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "skills" / "surface-status" / "scripts" / "surface_status"
PACKAGE = "surface_status"
NETWORK_MODULES = ("socket", "urllib", "http", "ssl")


def imported_modules(source: str) -> set[str]:
    """Name the top level module of every import in a source text, relative imports aside."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            found.add(node.module.split(".")[0])
    return found


def outside_the_standard_library(source: str) -> set[str]:
    return {
        name
        for name in imported_modules(source)
        if name not in sys.stdlib_module_names and name != PACKAGE
    }


def test_the_walk_flags_a_module_outside_the_standard_library() -> None:
    assert outside_the_standard_library("import json\nimport requests\n") == {"requests"}
    assert outside_the_standard_library("from yaml import safe_load\n") == {"yaml"}
    assert outside_the_standard_library("import os.path\nfrom surface_status import x\n") == set()
    assert outside_the_standard_library("def f():\n    import numpy\n") == {"numpy"}


def test_the_package_has_modules_to_walk() -> None:
    names = {path.stem for path in PACKAGE_DIR.glob("*.py")}
    assert {"cli", "record", "machine", "guards", "journal", "build", "report"} <= names


@pytest.mark.parametrize("path", sorted(PACKAGE_DIR.glob("*.py")), ids=lambda path: path.stem)
def test_every_import_of_the_package_is_the_standard_library(path: Path) -> None:
    assert outside_the_standard_library(path.read_text(encoding="utf-8")) == set(), path.name


@pytest.mark.parametrize("path", sorted(PACKAGE_DIR.glob("*.py")), ids=lambda path: path.stem)
def test_no_module_of_the_package_imports_a_network_module(path: Path) -> None:
    assert imported_modules(path.read_text(encoding="utf-8")) & set(NETWORK_MODULES) == set()


def test_ruff_bans_the_network_modules_in_the_package() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    banned = config["tool"]["ruff"]["lint"]["flake8-tidy-imports"]["banned-api"]
    assert set(NETWORK_MODULES) <= set(banned)
    ignored = config["tool"]["ruff"]["lint"]["per-file-ignores"]
    assert not [
        pattern for pattern in ignored if "surface_status" in pattern or "skills" in pattern
    ]


def test_every_cli_test_runs_with_the_sockets_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.socket().connect(("127.0.0.1", 9))


def test_a_command_completes_with_the_sockets_blocked(tmp_path: Path) -> None:
    project = Project(tmp_path)
    project.reach("interview")
    assert project.run().code == 0
    assert project.run("check", "--require", "conform").code == 1
