"""Installation by copy, the drift check and the namespace boundary (ADR 0019)."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from install_helpers import (
    GIT_ENV,
    ROOT,
    commit_all,
    git_init,
    load_installer,
    make_source,
    run_clone,
)

# Fake source, installer copied next to it so that the run is "from a clone".


def clone(tmp_path: Path) -> Path:
    source = make_source(tmp_path / "clone")
    (source / "install.py").write_bytes((ROOT / "install.py").read_bytes())
    return source


def tree(host: Path) -> dict[str, bytes]:
    return {
        path.relative_to(host).as_posix(): path.read_bytes()
        for path in sorted(host.rglob("*"))
        if path.is_file() and ".git/" not in path.as_posix()
    }


def test_install_on_fresh_git_init(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)

    result = run_clone(source, str(host))

    assert result.returncode == 0, result.stderr
    installed = tree(host)
    assert {name for name in installed if name.startswith(".claude/")} == {
        ".claude/skills/surface-plan/SKILL.md",
        ".claude/skills/surface-plan/templates/plan.md",
        ".claude/skills/surface-status/SKILL.md",
        ".claude/skills/surface-status/scripts/surface-status",
        ".claude/skills/surface-status/scripts/surface_status/__init__.py",
        ".claude/skills/surface-status/scripts/surface_status/cli.py",
        ".claude/agents/surface-checker.md",
        ".claude/agents/surface-executor.md",
    }  # no settings file, and never the Claude Code settings
    assert result.stdout.splitlines() == [
        f"control-surface installed in {host.resolve()} (8 files written)"
    ]
    launcher = host / ".claude/skills/surface-status/scripts/surface-status"
    assert launcher.stat().st_mode & 0o111
    assert not (host / ".claude/skills/surface-plan/SKILL.md").stat().st_mode & 0o111


def test_update_reports_files_written_and_removed(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))
    (host / ".claude/agents/surface-old.md").write_text("orphan\n", encoding="utf-8")
    commit_all(host)
    (source / "agents/surface-executor.md").write_text("executor, changed\n", encoding="utf-8")

    result = run_clone(source, str(host))

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"control-surface updated in {host.resolve()} (1 file written, 1 removed)"
    ]


def test_update_that_only_removes_reports_files_removed(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))
    (host / ".claude/agents/surface-old.md").write_text("orphan\n", encoding="utf-8")
    commit_all(host)

    result = run_clone(source, str(host))

    assert result.stdout.splitlines() == [
        f"control-surface updated in {host.resolve()} (1 file removed)"
    ]


def test_output_never_mentions_permissions_or_the_readme(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    (host / ".claude").mkdir()
    (host / ".claude/surface.md").write_text("# Critical zones\n", encoding="utf-8")
    outputs = [run_clone(source, str(host)).stdout]
    commit_all(host)
    outputs.append(run_clone(source, str(host)).stdout)
    (source / "agents/surface-executor.md").write_text("changed\n", encoding="utf-8")
    outputs.append(run_clone(source, str(host)).stdout)

    for output in outputs:
        assert "permission" not in output.lower()
        assert "github.com" not in output


def test_bytecode_never_copied(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"

    run_clone(source, str(host))

    leftovers = [
        name for name in tree(host) if "__pycache__" in name or name.endswith((".pyc", ".pyo"))
    ]
    assert leftovers == []


def test_reinstall_is_idempotent(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))
    commit_all(host)
    before = tree(host)

    again = run_clone(source, str(host))

    assert again.returncode == 0
    assert "already up to date" in again.stdout
    assert again.stdout.splitlines() == ["already up to date"]
    assert tree(host) == before
    assert run_clone(source, "--check", str(host)).returncode == 0


def test_check_passes_on_a_committed_installation(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))
    commit_all(host)

    result = run_clone(source, "--check", str(host))

    assert result.returncode == 0
    assert "no drift" in result.stdout


def test_check_reports_a_modified_installed_file(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))
    commit_all(host)
    modified = ".claude/skills/surface-plan/SKILL.md"
    (host / modified).write_text("edited in the host\n", encoding="utf-8")

    result = run_clone(source, "--check", str(host))

    assert result.returncode == 1
    assert f"drift : {modified}" in result.stdout
    assert f"uncommitted : {modified}" in result.stdout
    assert (host / modified).read_text(encoding="utf-8") == "edited in the host\n"  # writes nothing


def test_check_reports_a_missing_file(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    run_clone(source, str(host))
    (host / ".claude/agents/surface-checker.md").unlink()

    result = run_clone(source, "--check", str(host))

    assert result.returncode == 1
    assert "missing : .claude/agents/surface-checker.md" in result.stdout
    assert not (host / ".claude/agents/surface-checker.md").exists()


def test_check_reports_uncommitted_files(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))

    fresh = run_clone(source, "--check", str(host))

    assert fresh.returncode == 1
    assert "uncommitted : .claude/agents/surface-executor.md" in fresh.stdout
    assert "drift" not in fresh.stdout


def test_check_reports_an_installed_file_covered_by_gitignore(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))
    (host / ".gitignore").write_text(".claude/agents/\n", encoding="utf-8")
    commit_all(host)

    result = run_clone(source, "--check", str(host))

    assert result.returncode == 1
    assert "uncommitted : .claude/agents/surface-executor.md" in result.stdout


def test_check_finds_the_repository_of_a_host_below_its_root(tmp_path: Path) -> None:
    source = clone(tmp_path)
    repository = tmp_path / "repo"
    git_init(repository)
    host = repository / "packages" / "app"
    run_clone(source, str(host))
    commit_all(repository)
    assert run_clone(source, "--check", str(host)).returncode == 0

    (host / ".claude/agents/surface-checker.md").write_text("edited\n", encoding="utf-8")

    result = run_clone(source, "--check", str(host))
    assert "uncommitted : .claude/agents/surface-checker.md" in result.stdout


def test_check_outside_git_reports_no_uncommitted(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    run_clone(source, str(host))

    result = run_clone(source, "--check", str(host))

    assert result.returncode == 0, result.stdout


def test_orphan_is_reported_by_check_and_removed_by_install(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    run_clone(source, str(host))
    (source / "agents/surface-executor.md").unlink()
    (source / "skills/surface-plan/templates/plan.md").unlink()
    (source / "skills/surface-plan/templates").rmdir()

    checked = run_clone(source, "--check", str(host))

    assert checked.returncode == 1
    assert "orphan : .claude/agents/surface-executor.md" in checked.stdout
    assert "orphan : .claude/skills/surface-plan/templates/plan.md" in checked.stdout
    assert (host / ".claude/agents/surface-executor.md").exists()  # check wrote nothing

    installed = run_clone(source, str(host))

    assert installed.returncode == 0
    assert not (host / ".claude/agents/surface-executor.md").exists()
    assert not (host / ".claude/skills/surface-plan/templates").exists()
    assert run_clone(source, "--check", str(host)).returncode == 0


def test_a_skill_removed_from_the_source_is_removed_with_its_bytecode(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    run_clone(source, str(host))
    cache = host / ".claude/skills/surface-plan/templates/__pycache__"
    cache.mkdir()
    (cache / "helper.cpython-311.pyc").write_text("compiled by a run", encoding="utf-8")
    assert run_clone(source, "--check", str(host)).returncode == 0  # bytecode is not drift
    for path in sorted((source / "skills/surface-plan").rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    (source / "skills/surface-plan").rmdir()

    result = run_clone(source, str(host))

    assert result.returncode == 0
    assert not (host / ".claude/skills/surface-plan").exists()


def test_files_outside_the_namespace_are_never_touched(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    others = {
        ".claude/skills/other/SKILL.md": "another skill\n",
        ".claude/skills/other/scripts/run.py": "print(1)\n",
        ".claude/skills/surface/SKILL.md": "no dash after surface\n",
        ".claude/agents/reviewer.md": "another agent\n",
        ".claude/agents/surface.md": "no dash after surface\n",
        ".claude/settings.json": '{"hooks": {}}\n',
        ".claude/settings.local.json": "{}\n",
        "CLAUDE.md": "project rules\n",
    }
    for name, content in others.items():
        (host / name).parent.mkdir(parents=True, exist_ok=True)
        (host / name).write_text(content, encoding="utf-8")
    before = tree(host)

    assert run_clone(source, str(host)).returncode == 0
    assert run_clone(source, "--check", str(host)).returncode == 0
    assert run_clone(source, str(host)).returncode == 0

    after = tree(host)
    for name, content in others.items():
        assert after[name] == content.encode(), name
    assert set(before) <= set(after)


def test_non_namespace_sources_are_not_installed(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"

    run_clone(source, str(host))

    assert not (host / ".claude/skills/not-ours").exists()
    assert not (host / ".claude/agents/notes.md").exists()
    assert not (host / "README.md").exists()


def test_no_settings_file_is_created(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"

    run_clone(source, str(host))

    assert not (host / ".claude/surface.json").exists()
    assert not (host / ".claude/surface.md").exists()


def test_what_an_earlier_version_left_is_named_and_kept(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    (host / ".claude").mkdir(parents=True)
    settings = '{"gate_command": "make check", "mark_pr_ready": true, "plans_dir": "plans"}\n'
    (host / ".claude/surface.json").write_text(settings, encoding="utf-8")
    (host / ".claude/surface.md").write_text("# Critical zones\n", encoding="utf-8")

    result = run_clone(source, str(host))

    assert result.returncode == 0, result.stderr
    notes = [line for line in result.stdout.splitlines() if line.startswith("note : ")]
    assert len(notes) == 2
    assert notes[0].startswith("note : .claude/surface.md is no longer read; move what it")
    assert notes[0].endswith("to AGENTS.md or CLAUDE.md")
    assert notes[1].startswith("note : .claude/surface.json sets gate_command, mark_pr_ready,")
    assert notes[1].endswith("remove them (the gates are named by each plan)")
    assert (host / ".claude/surface.json").read_text(encoding="utf-8") == settings
    assert (host / ".claude/surface.md").read_text(encoding="utf-8") == "# Critical zones\n"


def test_settings_the_chain_still_reads_raise_no_note(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    (host / ".claude").mkdir(parents=True)
    (host / ".claude/surface.json").write_text('{"plans_dir": "plans"}', encoding="utf-8")

    result = run_clone(source, str(host))

    assert "note : " not in result.stdout


def test_a_host_of_a_single_file_or_a_missing_host_to_check_is_refused(tmp_path: Path) -> None:
    source = clone(tmp_path)
    (tmp_path / "file").write_text("x", encoding="utf-8")

    assert run_clone(source, str(tmp_path / "file")).returncode == 2
    assert run_clone(source, "--check", str(tmp_path / "absent")).returncode == 2
    assert run_clone(source).returncode == 2  # host is required from a clone


def test_a_directory_that_is_not_a_source_is_refused_before_anything_is_removed(
    tmp_path: Path,
) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    run_clone(source, str(host))
    (tmp_path / "bare").mkdir()
    (tmp_path / "bare" / "install.py").write_bytes((ROOT / "install.py").read_bytes())

    # Beside no sources the file is a lone script: it downloads, here from a missing local archive.
    missing = (tmp_path / "nowhere").as_uri() + "/{ref}.tar.gz"
    result = run_clone(tmp_path / "bare", str(host), "--archive-url", missing)

    assert result.returncode == 2
    assert (host / ".claude/agents/surface-checker.md").exists()


def test_old_python_gets_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installer = load_installer()
    monkeypatch.setattr(installer.sys, "version_info", (3, 9, 6, "final", 0))

    code = installer.main([str(tmp_path)], ROOT)

    assert code == 2
    assert "needs Python 3.11" in capsys.readouterr().err


def test_the_repository_installs_and_its_script_runs_without_settings(tmp_path: Path) -> None:
    host = tmp_path / "host"

    result = run_clone(ROOT, str(host))

    assert result.returncode == 0, result.stderr
    assert not (host / ".claude/surface.json").exists()
    script = host / ".claude/skills/surface-status/scripts/surface-status"
    listed = subprocess.run(
        [str(script), "--json"], cwd=host, capture_output=True, text=True, check=False
    )
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout) == {"v": 1, "plans": []}


def committed_install(tmp_path: Path) -> tuple[Path, Path]:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    run_clone(source, str(host))
    commit_all(host)
    return source, host


def test_install_refuses_to_overwrite_a_modified_file(tmp_path: Path) -> None:
    source, host = committed_install(tmp_path)
    modified = ".claude/skills/surface-plan/SKILL.md"
    (host / modified).write_text("local work\n", encoding="utf-8")
    (source / "agents/surface-checker.md").write_text("new checker\n", encoding="utf-8")

    result = run_clone(source, str(host))

    assert result.returncode == 2
    assert modified in result.stderr
    assert "--force" in result.stderr
    assert (host / modified).read_text(encoding="utf-8") == "local work\n"
    assert (host / ".claude/agents/surface-checker.md").read_text(
        encoding="utf-8"
    ) != "new checker\n"


def test_install_refuses_to_remove_an_untracked_orphan(tmp_path: Path) -> None:
    source, host = committed_install(tmp_path)
    orphan = ".claude/agents/surface-old.md"
    (host / orphan).write_text("never committed\n", encoding="utf-8")

    result = run_clone(source, str(host))

    assert result.returncode == 2
    assert orphan in result.stderr
    assert (host / orphan).exists()


def test_install_refuses_to_overwrite_an_untracked_file(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    target = host / ".claude/agents/surface-checker.md"
    target.parent.mkdir(parents=True)
    target.write_text("mine, not in git\n", encoding="utf-8")

    result = run_clone(source, str(host))

    assert result.returncode == 2
    assert ".claude/agents/surface-checker.md" in result.stderr
    assert target.read_text(encoding="utf-8") == "mine, not in git\n"
    assert not (host / ".claude/agents/surface-executor.md").exists()  # nothing was written


def test_force_overrides_the_guard(tmp_path: Path) -> None:
    source, host = committed_install(tmp_path)
    modified = host / ".claude/skills/surface-plan/SKILL.md"
    modified.write_text("local work\n", encoding="utf-8")
    orphan = host / ".claude/agents/surface-old.md"
    orphan.write_text("never committed\n", encoding="utf-8")

    result = run_clone(source, "--force", str(host))

    assert result.returncode == 0, result.stderr
    assert modified.read_text(encoding="utf-8") == "plan skill main\n"
    assert not orphan.exists()


def test_the_guard_does_not_apply_outside_git(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    run_clone(source, str(host))
    (host / ".claude/skills/surface-plan/SKILL.md").write_text("local\n", encoding="utf-8")

    assert run_clone(source, str(host)).returncode == 0


def test_nothing_outside_the_namespace_is_removed_even_when_unsaved(tmp_path: Path) -> None:
    source, host = committed_install(tmp_path)
    outside = {
        ".claude/agents/reviewer.md": "untracked agent\n",
        ".claude/skills/other/SKILL.md": "untracked skill\n",
        ".claude/settings.json": "{}\n",
    }
    for name, content in outside.items():
        (host / name).parent.mkdir(parents=True, exist_ok=True)
        (host / name).write_text(content, encoding="utf-8")
    (source / "agents/surface-executor.md").unlink()
    (host / ".claude/surface.md").write_text("edited settings\n", encoding="utf-8")

    result = run_clone(source, "--force", str(host))

    assert result.returncode == 0, result.stderr
    assert not (host / ".claude/agents/surface-executor.md").exists()
    for name, content in outside.items():
        assert (host / name).read_text(encoding="utf-8") == content
    assert (host / ".claude/surface.md").read_text(encoding="utf-8") == "edited settings\n"


# The guard fails closed: inside a git work tree, a git that cannot answer is a refusal.


def env_without_git(tmp_path: Path) -> dict[str, str]:
    empty = tmp_path / "no-git-here"
    empty.mkdir()
    return {**GIT_ENV, "PATH": str(empty)}


def env_with_broken_git(tmp_path: Path, message: str) -> dict[str, str]:
    """Put a `git` that refuses every command with a message ahead of the real one on the PATH."""
    shim = tmp_path / "broken-git"
    shim.mkdir()
    program = shim / "git"
    program.write_text(f"#!/bin/sh\necho '{message}' >&2\nexit 128\n", encoding="utf-8")
    program.chmod(0o755)
    return {**GIT_ENV, "PATH": f"{shim}{os.pathsep}{GIT_ENV['PATH']}"}


def refused_and_untouched(result: subprocess.CompletedProcess[str], host: Path) -> None:
    assert result.returncode == 2
    assert "--force" in result.stderr
    assert not (host / ".claude").exists()  # nothing was written


def test_install_refuses_when_git_is_missing_inside_a_work_tree(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)

    result = run_clone(source, str(host), env=env_without_git(tmp_path))

    refused_and_untouched(result, host)
    assert "git could not run" in result.stderr


def test_install_refuses_when_git_finds_dubious_ownership(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    message = "fatal: detected dubious ownership in repository"

    result = run_clone(source, str(host), env=env_with_broken_git(tmp_path, message))

    refused_and_untouched(result, host)
    assert "dubious ownership" in result.stderr


def test_install_refuses_when_git_fails_for_another_reason(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)
    (host / ".git/HEAD").write_text("garbage\n", encoding="utf-8")  # a repository git cannot read

    result = run_clone(source, str(host))

    refused_and_untouched(result, host)


def test_force_installs_when_git_cannot_answer(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"
    git_init(host)

    result = run_clone(source, "--force", str(host), env=env_without_git(tmp_path))

    assert result.returncode == 0, result.stderr
    assert (host / ".claude/agents/surface-checker.md").is_file()


def test_the_guard_does_not_apply_outside_git_even_without_git(tmp_path: Path) -> None:
    source = clone(tmp_path)
    host = tmp_path / "host"

    result = run_clone(source, str(host), env=env_without_git(tmp_path))

    assert result.returncode == 0, result.stderr
    assert (host / ".claude/agents/surface-checker.md").is_file()
