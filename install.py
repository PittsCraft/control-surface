#!/usr/bin/env python3
"""Install the control surface chain into a host project, or check it for drift.

From a clone:

    python3 install.py <host>            install or update
    python3 install.py --check <host>    write nothing, exit 1 on drift

From the public repository, into the current directory:

    curl -fsSL <raw URL of install.py on main> | python3 - [--check] [--ref <tag or commit>]

The exact one-line command sits at the top of the README.

Run this way, the installer downloads the archive of a version (`--ref`, `main` by default, a tag
or a commit) and installs from it as from a clone. `--archive-url` overrides where the archive
comes from; `{ref}` in it stands for the version.

Ownership is by namespace: the installer owns `.claude/skills/surface-*/` and
`.claude/agents/surface-*.md`. It removes owned files the source no longer has and never touches
anything else, in particular `.claude/surface.json` and `.claude/surface.md`, which it creates
only when they are missing. Unless `--force` is given, it also refuses to overwrite or remove an
owned file that has uncommitted changes or is not tracked by git.

Standard library only. Written to stay parseable by older interpreters so that the version
message below can be shown instead of a syntax error.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

MIN_PYTHON = (3, 11)
DEFAULT_REF = "main"
DEFAULT_ARCHIVE_URL = "https://github.com/PittsCraft/control-surface/archive/{ref}.tar.gz"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 60
NAMESPACE = "surface-"
SETTINGS = ("surface.json", "surface.md")
JUNK_NAMES = frozenset({"__pycache__", ".DS_Store"})
JUNK_SUFFIXES = (".pyc", ".pyo")
REF_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+-]*")
ALLOWED_URL_SCHEMES = ("https", "file")
EXIT_DRIFT = 1
EXIT_USAGE = 2
# The installer never writes the host's Claude Code settings: it points at the rules instead.
PERMISSIONS_HINT = (
    "Before your first /surface-execute, allow what the loop runs:"
    " https://github.com/PittsCraft/control-surface#permissions"
)


class InstallError(Exception):
    """A problem the user can act on, reported in one line."""


def say(message: str) -> None:
    sys.stdout.write(message + "\n")


def is_junk(path: Path) -> bool:
    """Bytecode and file manager leftovers: never copied, never reported."""
    return path.name in JUNK_NAMES or path.name.endswith(JUNK_SUFFIXES)


def has_junk_part(relative: Path) -> bool:
    return any(is_junk(Path(part)) for part in relative.parts)


# Source side


def check_source(source: Path) -> None:
    for name in SETTINGS:
        if not (source / "templates" / name).is_file():
            message = f"{source} is not a control-surface source (templates/{name} is missing)"
            raise InstallError(message)


def expected_files(source: Path) -> dict[str, Path]:
    """Host relative path (posix) to source file, for every file the installer owns."""
    found: dict[str, Path] = {}
    skills = source / "skills"
    if skills.is_dir():
        for skill in sorted(skills.glob(NAMESPACE + "*")):
            if not skill.is_dir():
                continue
            for path in sorted(skill.rglob("*")):
                relative = path.relative_to(skills)
                if path.is_file() and not has_junk_part(relative):
                    found[(PurePosixPath(".claude/skills") / relative.as_posix()).as_posix()] = path
    agents = source / "agents"
    if agents.is_dir():
        for path in sorted(agents.glob(NAMESPACE + "*.md")):
            if path.is_file():
                found[f".claude/agents/{path.name}"] = path
    return found


def is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


# Host side


def skill_files(host: Path, skill: Path) -> set[str]:
    """Owned entries under one installed skill; a symlink counts as one entry, never followed."""
    if skill.is_symlink() or not skill.is_dir():
        return {skill.relative_to(host).as_posix()}
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(skill):
        directory = Path(dirpath)
        links = [name for name in dirnames if (directory / name).is_symlink()]
        dirnames[:] = [name for name in dirnames if name not in links and not is_junk(Path(name))]
        names = [*filenames, *links]
        found.update(
            (directory / name).relative_to(host).as_posix()
            for name in names
            if not is_junk(Path(name))
        )
    return found


def owned_files(host: Path) -> set[str]:
    """Host relative path (posix) of every entry in the installer's namespace, as on disk."""
    found: set[str] = set()
    skills = host / ".claude" / "skills"
    if skills.is_dir():
        for skill in skills.glob(NAMESPACE + "*"):
            found |= skill_files(host, skill)
    agents = host / ".claude" / "agents"
    if agents.is_dir():
        found.update(path.relative_to(host).as_posix() for path in agents.glob(NAMESPACE + "*.md"))
    return found


def same_as_source(source_file: Path, dest: Path) -> bool:
    if dest.is_symlink() or not dest.is_file():
        return False
    return dest.read_bytes() == source_file.read_bytes() and (
        is_executable(dest) == is_executable(source_file)
    )


class GitUnavailableError(Exception):
    """git cannot answer for a host that sits in a git work tree."""


def inside_git_tree(host: Path) -> bool:
    """Whether a `.git` (a folder, or a file for a linked work tree) sits in the host or above it.

    Read from the file system, since it must hold when git itself cannot run or refuses to read.
    """
    real_host = host.resolve()
    return any((folder / ".git").exists() for folder in (real_host, *real_host.parents))


def git_output(host: Path, *args: str) -> str | None:
    """Return the output of a git command run in the host.

    None when the host sits outside any git work tree. Raises GitUnavailableError when it sits in
    one and git cannot answer: git missing, "dubious ownership", any other failure.
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(host), *args],  # noqa: S607
            capture_output=True,
            check=False,
        )
    except OSError as error:
        reason = f"git could not run: {error}"
    else:
        if result.returncode == 0:
            return result.stdout.decode("utf-8", errors="surrogateescape")
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        reason = detail or f"git exited with status {result.returncode}"
    if not inside_git_tree(host):
        return None
    raise GitUnavailableError(reason)


def uncommitted(host: Path, relatives: set[str]) -> set[str]:
    """Paths among `relatives` that git shows as modified, staged, untracked or ignored.

    Empty when the host is not a git work tree; GitUnavailableError when it is one and git cannot
    answer. An installation is only finished once it is committed, and an owned file covered by a
    .gitignore stays out of history for good.
    """
    top = git_output(host, "rev-parse", "--show-toplevel")
    if top is None:
        return set()
    top_path = Path(top.strip()).resolve()
    real_host = host.resolve()
    listing = git_output(
        host,
        "status",
        "--porcelain=v1",
        "-z",
        "--ignored",
        "--untracked-files=all",
        "--",
        ".claude/skills",
        ".claude/agents",
    )
    if listing is None:
        return set()
    entries = listing.split("\0")
    dirty: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:  # noqa: PLR2004 - "XY path" is at least four characters
            continue
        if entry[0] in "RC" or entry[1] in "RC":
            index += 1  # a rename or copy is followed by the original path
        try:
            relative = (top_path / entry[3:]).relative_to(real_host).as_posix()
        except ValueError:
            continue
        dirty.add(relative)
    return dirty & relatives


def check(source: Path, host: Path) -> list[str]:
    """One line per difference between the host and the source; nothing is written."""
    expected = expected_files(source)
    lines: list[str] = []
    present: set[str] = set()
    for relative, source_file in expected.items():
        dest = host / relative
        if not (dest.exists() or dest.is_symlink()):
            lines.append(f"missing : {relative}")
        else:
            present.add(relative)
            if not same_as_source(source_file, dest):
                lines.append(f"drift : {relative}")
    lines.extend(f"orphan : {relative}" for relative in sorted(owned_files(host) - set(expected)))
    dirty: set[str]
    try:
        dirty = uncommitted(host, present)
    except GitUnavailableError:
        # A check writes nothing: it reports the drift it can see, and install is what refuses.
        dirty = set()
    lines.extend(f"uncommitted : {relative}" for relative in sorted(dirty))
    return lines


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def only_junk(directory: Path) -> bool:
    return all(
        is_junk(path) or has_junk_part(path.relative_to(directory))
        for path in directory.rglob("*")
        if not path.is_dir()
    )


def prune(host: Path, expected: dict[str, Path]) -> None:
    """Remove directories of the namespace that the source no longer has and no file fills."""
    skills = host / ".claude" / "skills"
    if not skills.is_dir():
        return
    kept_roots = {
        PurePosixPath(relative).parts[2] for relative in expected if "/skills/" in relative
    }
    kept_dirs = {
        (host / parent).as_posix()
        for relative in expected
        for parent in PurePosixPath(relative).parents
    }
    for skill in skills.glob(NAMESPACE + "*"):
        if skill.is_symlink() or not skill.is_dir():
            continue
        if skill.name not in kept_roots:
            shutil.rmtree(skill)
            continue
        for dirpath, _dirnames, _filenames in os.walk(skill, topdown=False):
            directory = Path(dirpath)
            if (
                directory != skill
                and directory.as_posix() not in kept_dirs
                and only_junk(directory)
            ):
                shutil.rmtree(directory)


def write_file(source_file: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
    dest.write_bytes(source_file.read_bytes())
    mode = dest.stat().st_mode & 0o777
    dest.chmod(mode | 0o111 if is_executable(source_file) else mode & ~0o111)


def create_missing_settings(source: Path, host: Path) -> list[str]:
    """Copy each settings template when the host has nothing at that path, never otherwise."""
    created: list[str] = []
    for name in SETTINGS:
        dest = host / ".claude" / name
        if dest.exists() or dest.is_symlink():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as handle:
            handle.write((source / "templates" / name).read_bytes())
        created.append(f".claude/{name}")
    return created


def refuse_unsaved_work(host: Path, touched: set[str]) -> None:
    """Refuse to overwrite or remove files git does not hold safely (committed and unmodified).

    Outside a git work tree there is nothing to ask, and the guard does not apply. Inside one, when
    git cannot answer, the guard refuses too: it cannot tell that nothing would be lost.
    """
    try:
        unsaved = sorted(uncommitted(host, touched))
    except GitUnavailableError as error:
        message = (
            f"refusing to install: git cannot tell whether files hold unsaved work ({error})\n"
            "fix git for this folder, or run again with --force to install without the check"
        )
        raise InstallError(message) from error
    if unsaved:
        listing = "\n".join(f"  {relative}" for relative in unsaved)
        message = (
            "refusing to overwrite or remove files with unsaved work (uncommitted or untracked):\n"
            f"{listing}\ncommit or stash them, or run again with --force to discard them"
        )
        raise InstallError(message)


def install(source: Path, host: Path, *, force: bool = False) -> list[str]:
    """Copy the chain into the host; returns one line per change, empty when up to date.

    Before writing or removing anything, refuses when a file it would overwrite or remove has
    unsaved work in git, unless `force`. Only paths of the namespace are ever removed.
    """
    expected = expected_files(source)
    stale = [
        relative
        for relative, source_file in expected.items()
        if not same_as_source(source_file, host / relative)
    ]
    orphans = sorted(owned_files(host) - set(expected))
    if not force:
        refuse_unsaved_work(host, {*stale, *orphans})
    lines: list[str] = []
    for relative in stale:
        write_file(expected[relative], host / relative)
        lines.append(f"written : {relative}")
    for relative in orphans:
        remove_path(host / relative)
        lines.append(f"removed : {relative}")
    prune(host, expected)
    lines.extend(f"created : {relative}" for relative in create_missing_settings(source, host))
    return lines


# Download side


def archive_url(template: str, ref: str) -> str:
    if REF_PATTERN.fullmatch(ref) is None or ".." in ref:
        message = f"invalid version {ref!r}: expected a branch, a tag or a commit"
        raise InstallError(message)
    url = template.replace("{ref}", ref)
    if urllib.parse.urlparse(url).scheme not in ALLOWED_URL_SCHEMES:
        message = f"unsupported archive URL {url!r}: use https or file"
        raise InstallError(message)
    return url


def download(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:  # noqa: S310
            data: bytes = response.read(MAX_ARCHIVE_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError) as error:
        message = f"cannot download {url}: {error}"
        raise InstallError(message) from error
    if len(data) > MAX_ARCHIVE_BYTES:
        message = f"archive at {url} is larger than {MAX_ARCHIVE_BYTES} bytes"
        raise InstallError(message)
    return data


def unpack(data: bytes, into: Path) -> Path:
    """Unpack a tar.gz whose files share one top directory; returns that directory.

    Only regular files and directories are written, through paths checked to stay inside `into`,
    so a hostile archive cannot write elsewhere.
    """
    try:
        archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")  # noqa: SIM115
    except (tarfile.TarError, OSError, EOFError) as error:
        message = f"the downloaded archive is not a readable tar.gz: {error}"
        raise InstallError(message) from error
    root = into / "source"
    root.mkdir()
    with archive:
        try:
            for member in archive:
                parts = PurePosixPath(member.name).parts
                if len(parts) < 2 and not member.isdir():  # noqa: PLR2004
                    continue
                inner = parts[1:]
                if not inner:
                    continue
                if PurePosixPath(member.name).is_absolute() or ".." in inner:
                    message = f"unsafe path in the archive: {member.name!r}"
                    raise InstallError(message)
                target = root.joinpath(*inner)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    handle = archive.extractfile(member)
                    if handle is None:
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(handle.read())
                    target.chmod(0o755 if member.mode & 0o111 else 0o644)
        except (tarfile.TarError, OSError, EOFError) as error:
            message = f"the downloaded archive is damaged: {error}"
            raise InstallError(message) from error
    return root


# Entry point


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install.py",
        description="Install the control surface chain into a host project, or check drift.",
    )
    parser.add_argument(
        "host", nargs="?", help="host project (default: current directory when downloading)"
    )
    parser.add_argument("--check", action="store_true", help="write nothing, exit 1 on drift")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite or remove files even with uncommitted changes in git",
    )
    parser.add_argument(
        "--ref",
        help=f"version to download: a branch, a tag or a commit (default: {DEFAULT_REF})",
    )
    parser.add_argument(
        "--archive-url",
        help="archive to download instead of the public repository's; {ref} stands for the version",
    )
    return parser


def run(source: Path, host: Path, *, check_only: bool, force: bool = False) -> int:
    check_source(source)
    if check_only:
        if not host.is_dir():
            message = f"{host} is not a directory"
            raise InstallError(message)
        lines = check(source, host)
        for line in lines:
            say(line)
        if lines:
            return EXIT_DRIFT
        say("no drift: the installation matches the source.")
        return 0
    if host.exists() and not host.is_dir():
        message = f"{host} is not a directory"
        raise InstallError(message)
    host.mkdir(parents=True, exist_ok=True)
    lines = install(source, host.resolve(), force=force)
    for line in lines:
        say(line)
    say(f"control-surface installed in {host.resolve()}" if lines else "already up to date")
    say(PERMISSIONS_HINT)
    return 0


def main(argv: list[str], clone_root: Path | None) -> int:
    """`clone_root` is the directory holding the sources, or None when run from standard input."""
    if sys.version_info < MIN_PYTHON:
        sys.stderr.write(
            "install.py needs Python "
            + ".".join(map(str, MIN_PYTHON))
            + f" or newer, this is {sys.version_info[0]}.{sys.version_info[1]}\n",
        )
        return EXIT_USAGE
    parser = build_parser()
    args = parser.parse_args(argv)
    downloading = clone_root is None or args.ref is not None or args.archive_url is not None
    if args.host is None and not downloading:
        parser.error("the host project is required when installing from a clone")
    host = Path(args.host if args.host is not None else Path.cwd())
    try:
        if not downloading:
            assert clone_root is not None  # noqa: S101 - `downloading` is False only for a clone
            return run(clone_root, host, check_only=args.check, force=args.force)
        ref = DEFAULT_REF if args.ref is None else args.ref
        url = archive_url(args.archive_url or DEFAULT_ARCHIVE_URL, ref)
        data = download(url)
        with tempfile.TemporaryDirectory(prefix="control-surface-") as directory:
            return run(unpack(data, Path(directory)), host, check_only=args.check, force=args.force)
    except InstallError as error:
        sys.stderr.write(f"install.py: {error}\n")
        return EXIT_USAGE


if __name__ == "__main__":
    # Under `python3 -` there is no __file__: the script came from standard input.
    script = globals().get("__file__")
    sys.exit(main(sys.argv[1:], Path(script).resolve().parent if script else None))
