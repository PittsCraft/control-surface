"""Repository text rules: no em dash in any text file of the repository."""

import subprocess
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

EM_DASH = chr(0x2014)  # a code point, so this file holds no literal em dash
ROOT = Path(__file__).resolve().parents[2]


def files_with_em_dash(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue  # binary, or a path git lists but the tree no longer holds
        if EM_DASH in text:
            found.append(path)
    return found


def repository_files() -> list[Path]:
    """Tracked files plus untracked ones that are not ignored, so new files are checked too."""
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return [ROOT / name for name in listing.split("\0") if name]


def test_no_em_dash_in_repository() -> None:
    offenders = files_with_em_dash(repository_files())
    assert not offenders, f"em dash found in: {[str(p.relative_to(ROOT)) for p in offenders]}"


@given(st.text().filter(lambda text: EM_DASH not in text), st.text(), st.text())
def test_detector_finds_an_inserted_em_dash(clean: str, before: str, after: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        good = Path(directory) / "good.txt"
        bad = Path(directory) / "bad.txt"
        good.write_text(clean, encoding="utf-8", newline="")
        bad.write_text(before + EM_DASH + after, encoding="utf-8", newline="")
        assert files_with_em_dash([good, bad]) == [bad]
