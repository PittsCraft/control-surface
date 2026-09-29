"""Shared helpers of the installer tests: a fake source, archives, git hosts, runners."""

import importlib.util
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
INSTALL_PY = ROOT / "install.py"
ONE_LINE = (
    "curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py"
    " | python3 -"
)
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def load_installer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_source(root: Path, label: str = "main") -> Path:
    """Build a fake source tree: the shape of the repository, with dummy files."""
    files = {
        "templates/surface.json": '{\n  "gate_command": null\n}\n',
        "templates/surface.md": "# Project declarations\n",
        "skills/surface-plan/SKILL.md": f"plan skill {label}\n",
        "skills/surface-plan/templates/plan.md": "plan template\n",
        "skills/surface-status/SKILL.md": f"status skill {label}\n",
        "skills/surface-status/scripts/surface-status": "#!/bin/sh\necho status\n",
        "skills/surface-status/scripts/surface_status/__init__.py": "",
        "skills/surface-status/scripts/surface_status/cli.py": f"LABEL = {label!r}\n",
        "skills/surface-status/scripts/surface_status/__pycache__/cli.cpython-311.pyc": "junk",
        "skills/surface-status/scripts/surface_status/stale.pyc": "junk",
        "skills/not-ours/SKILL.md": "outside the namespace\n",
        "agents/surface-checker.md": f"checker {label}\n",
        "agents/surface-executor.md": "executor\n",
        "agents/notes.md": "outside the namespace\n",
        "README.md": "not installed\n",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "skills/surface-status/scripts/surface-status").chmod(0o755)
    return root


def make_archive(source: Path, destination: Path, top: str) -> None:
    """Write a GitHub style archive: every path under one top directory."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(source, arcname=top)
    destination.write_bytes(buffer.getvalue())


def git(host: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(host), *args],  # noqa: S607
        capture_output=True,
        check=True,
        text=True,
        env=GIT_ENV,
    ).stdout


def git_init(host: Path) -> None:
    host.mkdir(parents=True, exist_ok=True)
    git(host, "init", "-q")


def commit_all(host: Path) -> None:
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "install", "--allow-empty")


def run_clone(
    source: Path, *args: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run `python3 install.py` the way a clone does: the file sits next to the sources."""
    return subprocess.run(
        [sys.executable, str(source / "install.py"), *args],
        capture_output=True,
        check=False,
        text=True,
        cwd=cwd,
        env=env or GIT_ENV,
    )


def run_piped(
    *args: str, cwd: Path, archive_dir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the installer as `curl ... | python3 -` does: the script arrives on standard input."""
    extra = ["--archive-url", archive_dir.as_uri() + "/{ref}.tar.gz"] if archive_dir else []
    return subprocess.run(
        [sys.executable, "-", *extra, *args],
        input=INSTALL_PY.read_text(encoding="utf-8"),
        capture_output=True,
        check=False,
        text=True,
        cwd=cwd,
        env=GIT_ENV,
    )
