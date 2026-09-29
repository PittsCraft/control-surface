"""ADR 0027: the installer fed through standard input, from a directory that is no clone."""

import sys
from pathlib import Path

import pytest
from install_helpers import (
    ONE_LINE,
    ROOT,
    commit_all,
    git_init,
    load_installer,
    make_archive,
    make_source,
    other_pythons,
    run_clone,
    run_piped,
    run_piped_default,
)

COMMIT = "3f2a9c1d5e7b40a86c1d2e3f4a5b6c7d8e9f0a1b"


@pytest.fixture
def archives(tmp_path: Path) -> Path:
    """Local archives standing for the public repository: one per version, each with its label."""
    directory = tmp_path / "archives"
    directory.mkdir()
    for ref in ("main", "v1.2.0", COMMIT):
        source = make_source(tmp_path / f"source-{ref}", label=ref)
        make_archive(source, directory / f"{ref}.tar.gz", top=f"control-surface-{ref}")
    return directory


def installed_label(host: Path) -> str:
    return (host / ".claude/skills/surface-plan/SKILL.md").read_text(encoding="utf-8")


def test_the_readme_opens_with_the_one_line_install() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    first_block = readme.split("```sh\n", 1)[1].split("```", 1)[0].strip()

    assert first_block == ONE_LINE


def test_piped_install_into_the_current_directory_for_main(tmp_path: Path, archives: Path) -> None:
    host = tmp_path / "not-a-clone"
    git_init(host)

    result = run_piped(cwd=host, archive_dir=archives)

    assert result.returncode == 0, result.stderr
    assert installed_label(host) == "plan skill main\n"
    assert (host / ".claude/agents/surface-checker.md").is_file()
    assert (host / ".claude/surface.json").is_file()
    assert (host / ".claude/skills/surface-status/scripts/surface-status").stat().st_mode & 0o111
    assert not (host / "install.py").exists()
    assert not (host / "README.md").exists()  # only owned files and settings land in the host


@pytest.mark.parametrize("ref", ["v1.2.0", COMMIT])
def test_piped_install_of_a_tag_or_a_commit(tmp_path: Path, archives: Path, ref: str) -> None:
    host = tmp_path / "host"
    host.mkdir()

    result = run_piped("--ref", ref, cwd=host, archive_dir=archives)

    assert result.returncode == 0, result.stderr
    assert installed_label(host) == f"plan skill {ref}\n"


def test_piped_update_replaces_a_previous_version(tmp_path: Path, archives: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    run_piped("--ref", "v1.2.0", cwd=host, archive_dir=archives)

    result = run_piped(cwd=host, archive_dir=archives)

    assert result.returncode == 0, result.stderr
    assert installed_label(host) == "plan skill main\n"


def test_piped_check_passes_after_a_piped_install(tmp_path: Path, archives: Path) -> None:
    host = tmp_path / "host"
    git_init(host)
    run_piped(cwd=host, archive_dir=archives)
    commit_all(host)

    result = run_piped("--check", cwd=host, archive_dir=archives)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no drift" in result.stdout


def test_piped_check_of_another_version_reports_drift(tmp_path: Path, archives: Path) -> None:
    host = tmp_path / "host"
    git_init(host)
    run_piped("--ref", "v1.2.0", cwd=host, archive_dir=archives)
    commit_all(host)

    result = run_piped("--check", cwd=host, archive_dir=archives)

    assert result.returncode == 1
    assert "drift : .claude/skills/surface-plan/SKILL.md" in result.stdout


def test_piped_check_reports_drift_exactly_as_a_clone_does(tmp_path: Path, archives: Path) -> None:
    clone = make_source(tmp_path / "clone")
    (clone / "install.py").write_bytes((ROOT / "install.py").read_bytes())
    host = tmp_path / "host"
    git_init(host)
    run_clone(clone, str(host))
    commit_all(host)
    (host / ".claude/skills/surface-plan/SKILL.md").write_text("edited\n", encoding="utf-8")
    (host / ".claude/agents/surface-executor.md").unlink()
    (host / ".claude/agents/surface-old.md").write_text("orphan\n", encoding="utf-8")

    from_clone = run_clone(clone, "--check", str(host))
    piped = run_piped("--check", cwd=host, archive_dir=archives)

    assert from_clone.returncode == piped.returncode == 1
    assert piped.stdout == from_clone.stdout
    for line in (
        "drift : .claude/skills/surface-plan/SKILL.md",
        "missing : .claude/agents/surface-executor.md",
        "orphan : .claude/agents/surface-old.md",
        "uncommitted : .claude/skills/surface-plan/SKILL.md",
    ):
        assert line in piped.stdout


def test_piped_check_writes_nothing(tmp_path: Path, archives: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()

    result = run_piped("--check", cwd=host, archive_dir=archives)

    assert result.returncode == 1
    assert list(host.iterdir()) == []


def test_ref_flag_makes_a_clone_download_too(tmp_path: Path, archives: Path) -> None:
    clone = make_source(tmp_path / "clone")
    (clone / "install.py").write_bytes((ROOT / "install.py").read_bytes())
    host = tmp_path / "host"

    result = run_clone(
        clone, str(host), "--ref", "v1.2.0", "--archive-url", archives.as_uri() + "/{ref}.tar.gz"
    )

    assert result.returncode == 0, result.stderr
    assert installed_label(host) == "plan skill v1.2.0\n"


@pytest.mark.parametrize("ref", ["../etc", "-x", "a b", "", "v1;rm"])
def test_an_invalid_version_is_refused(tmp_path: Path, archives: Path, ref: str) -> None:
    host = tmp_path / "host"
    host.mkdir()

    result = run_piped("--ref", ref, cwd=host, archive_dir=archives)

    assert result.returncode == 2
    assert list(host.iterdir()) == []


def test_an_unknown_version_is_a_clean_failure(tmp_path: Path, archives: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()

    result = run_piped("--ref", "v9.9.9", cwd=host, archive_dir=archives)

    assert result.returncode == 2
    assert "cannot download" in result.stderr
    assert "Traceback" not in result.stderr
    assert list(host.iterdir()) == []


def test_a_bad_archive_touches_nothing(tmp_path: Path, archives: Path) -> None:
    (archives / "broken.tar.gz").write_bytes(b"not an archive")
    make_archive(tmp_path, archives / "empty.tar.gz", top="empty")  # a tree with no templates
    host = tmp_path / "host"
    host.mkdir()

    broken = run_piped("--ref", "broken", cwd=host, archive_dir=archives)
    empty = run_piped("--ref", "empty", cwd=host, archive_dir=archives)

    assert broken.returncode == empty.returncode == 2
    assert "Traceback" not in broken.stderr + empty.stderr
    assert list(host.iterdir()) == []


def test_only_https_and_file_urls_are_accepted(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()

    result = run_piped("--archive-url", "ftp://example.com/{ref}.tar.gz", cwd=host)

    assert result.returncode == 2
    assert "unsupported archive URL" in result.stderr


def test_the_default_archive_is_the_public_repository() -> None:
    installer = load_installer()

    assert (
        installer.archive_url(installer.DEFAULT_ARCHIVE_URL, "main")
        == "https://github.com/PittsCraft/control-surface/archive/main.tar.gz"
    )
    assert installer.archive_url(installer.DEFAULT_ARCHIVE_URL, "feature/x").endswith(
        "/archive/feature/x.tar.gz"
    )


# Every interpreter the piped run is checked on: the running one, and another one when available.
PYTHONS = [sys.executable, *other_pythons()]


@pytest.mark.parametrize("python", PYTHONS)
def test_documented_one_line_install_from_an_empty_repository(
    tmp_path: Path, archives: Path, python: str
) -> None:
    """No flags at all, as in the README: `python3 -` must download, not assume a clone."""
    host = tmp_path / "host"
    git_init(host)

    result = run_piped_default(cwd=host, archive_dir=archives, tmp=tmp_path, python=python)

    assert result.returncode == 0, result.stderr
    assert installed_label(host) == "plan skill main\n"


@pytest.mark.parametrize("python", PYTHONS)
def test_documented_one_line_check_from_a_repository(
    tmp_path: Path, archives: Path, python: str
) -> None:
    host = tmp_path / "host"
    git_init(host)
    run_piped_default(cwd=host, archive_dir=archives, tmp=tmp_path, python=python)
    commit_all(host)

    result = run_piped_default(
        "--check", cwd=host, archive_dir=archives, tmp=tmp_path, python=python
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no drift" in result.stdout


def test_a_stdin_file_name_is_not_a_clone(tmp_path: Path) -> None:
    installer = load_installer()
    clone = make_source(tmp_path / "clone")
    (clone / "install.py").write_text("", encoding="utf-8")

    assert installer.find_clone_root("<stdin>") is None
    assert installer.find_clone_root(None) is None
    assert installer.find_clone_root(str(tmp_path / "missing.py")) is None
    lone = tmp_path / "lone"
    lone.mkdir()
    (lone / "install.py").write_text("", encoding="utf-8")
    assert installer.find_clone_root(str(lone / "install.py")) is None
    assert installer.find_clone_root(str(clone / "install.py")) == clone.resolve()
