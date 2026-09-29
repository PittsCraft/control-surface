"""Replay reads no other file. Checked by signature, by imports, and by running it blind."""

import ast
import builtins
import inspect
import os
from collections.abc import Iterable
from pathlib import Path
from typing import get_type_hints

import pytest
from state_support import FIXTURES, load_journal, replay

from surface_status import events, guards, machine
from surface_status.events import Event
from surface_status.guards import fold

PURE_MODULES = (events, machine, guards)
ALLOWED_IMPORTS = {"collections.abc", "dataclasses", "enum", "typing"}


def test_fold_takes_a_sequence_of_events_and_nothing_else() -> None:
    parameters = inspect.signature(fold).parameters
    assert list(parameters) == ["events"]
    assert get_type_hints(fold)["events"] == Iterable[Event]


@pytest.mark.parametrize("module", PURE_MODULES, ids=lambda module: module.__name__)
def test_the_core_imports_nothing_that_could_touch_the_world(module: object) -> None:
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")  # type: ignore[arg-type]
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    foreign = {name for name in imported if not name.startswith("surface_status")}
    assert foreign <= ALLOWED_IMPORTS, foreign


@pytest.mark.parametrize("module", PURE_MODULES, ids=lambda module: module.__name__)
def test_the_core_does_not_call_open_print_or_input(module: object) -> None:
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")  # type: ignore[arg-type]
    called = {
        node.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called & {"open", "print", "input", "exec", "eval", "__import__"}


def test_replay_gives_the_same_state_from_an_empty_directory_with_no_file_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = load_journal(FIXTURES / "break-accepted-then-resumed.jsonl")
    expected = replay(journal)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "replay must not touch the file system"
        raise AssertionError(message)

    monkeypatch.chdir(tmp_path)
    for name in ("open", "input"):
        monkeypatch.setattr(builtins, name, forbidden)
    for name in ("stat", "listdir", "scandir"):
        monkeypatch.setattr(os, name, forbidden)
    assert fold(journal) == expected
    assert fold(journal) == fold(journal)
