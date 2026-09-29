"""The launcher: one path to call, and a clear refusal of a Python below 3.11."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from cli_support import Project

LAUNCHER = (
    Path(__file__).resolve().parents[2] / "skills" / "surface-status" / "scripts" / "surface-status"
)


def _run(project: Project, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ}
    if path is not None:
        environment["PATH"] = path
    return subprocess.run(
        [str(LAUNCHER), "--root", str(project.root), *args],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        cwd=project.root,
    )


def _fake_python(folder: Path, version_check_exit: int) -> str:
    """Put a `python3` first on the PATH that fails the version check like an old Python does."""
    folder.mkdir()
    fake = folder / "python3"
    fake.write_text(f"#!/bin/sh\nexit {version_check_exit}\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return str(folder) + os.pathsep + "/usr/bin:/bin"


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path / "host")


def test_the_launcher_is_executable() -> None:
    assert LAUNCHER.stat().st_mode & stat.S_IXUSR


def test_the_launcher_runs_the_cli_and_passes_the_exit_code(project: Project) -> None:
    project.reach("executing")
    listed = _run(project, "--json")
    assert listed.returncode == 0
    assert '"state": "executing"' in listed.stdout
    refused = _run(
        project, "record", "2026-09-29-feature", "slice-done", "--slice", "9", "--gates", "x"
    )
    assert refused.returncode == 1
    usage = _run(project, "record")
    assert usage.returncode == 2


def test_the_launcher_writes_no_bytecode_next_to_the_installed_script(
    project: Project, tmp_path: Path
) -> None:
    installed = tmp_path / "installed"
    shutil.copytree(
        LAUNCHER.parent, installed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    project.reach("interview")
    environment = {
        key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"
    }
    ran = subprocess.run(
        [str(installed / "surface-status"), "--root", str(project.root), "--json"],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        cwd=project.root,
    )
    assert ran.returncode == 0, ran.stderr
    assert not list(installed.rglob("__pycache__"))


def test_the_launcher_refuses_python_below_3_11_with_one_line_and_code_2(
    project: Project, tmp_path: Path
) -> None:
    result = _run(project, path=_fake_python(tmp_path / "old", version_check_exit=1))
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1
    assert "3.11" in result.stderr


def test_the_launcher_refuses_a_missing_python_the_same_way(
    project: Project, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    sh = "/bin/sh"
    result = subprocess.run(
        [sh, str(LAUNCHER)],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": str(empty)},
        cwd=project.root,
    )
    assert result.returncode == 2
    assert len(result.stderr.splitlines()) == 1


def test_the_test_run_itself_is_on_a_supported_python() -> None:
    assert sys.version_info >= (3, 11)
