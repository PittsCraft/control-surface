"""The repository holds the product alone: nothing private leaks into a file it tracks.

The chain was designed and built in a private workspace. What stays there, the working documents
of the design, the other projects of its author and the paths of their machine, must never reach
a file of this repository, so every tracked or untracked file that is not ignored is read, and
matched without regard to case.
"""

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from test_repo_text import ROOT, repository_files

# Each marker names what it keeps out. The list stays short: a marker is a signal, the review
# reads the rest.
MARKERS = (
    "tender",  # a private project the chain was first meant for
    "charpente",  # the private workspace template of the author
    "pierremardon",  # the author's account on their machine
    "/Users/",  # a home directory, hence a path of someone's machine
    "docs/plans/2026-",  # the folders of the design work, kept private
    "bootstrap plan",  # the name of that design work
)
# The author's first name, allowed only in the copyright notice.
AUTHOR = "pierre"
AUTHOR_ALLOWED = frozenset({"LICENSE"})
# This file names the markers it looks for, so it cannot be read for them.
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()


def markers_in(text: str, *, author_allowed: bool = False) -> set[str]:
    lowered = text.lower()
    found = {marker for marker in MARKERS if marker.lower() in lowered}
    if not author_allowed and AUTHOR in lowered:
        found.add(AUTHOR)
    return found


def leaks(paths: list[Path]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        if name == SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue  # binary, or a path git lists but the tree no longer holds
        markers = markers_in(text, author_allowed=name in AUTHOR_ALLOWED)
        if markers:
            found[name] = markers
    return found


def test_no_private_marker_in_the_repository() -> None:
    assert leaks(repository_files()) == {}


def test_the_author_is_named_in_the_license() -> None:
    assert AUTHOR in (ROOT / "LICENSE").read_text(encoding="utf-8").lower()


@given(
    marker=st.sampled_from((*MARKERS, AUTHOR)),
    before=st.text(),
    after=st.text(),
    upper=st.booleans(),
)
def test_the_detector_finds_an_inserted_marker(
    marker: str, before: str, after: str, *, upper: bool
) -> None:
    inserted = marker.upper() if upper else marker
    assert marker in markers_in(before + inserted + after)


def test_the_license_may_name_the_author_and_nothing_else() -> None:
    assert markers_in("Copyright (c) Pierre", author_allowed=True) == set()
    assert markers_in("Pierre, see /Users/", author_allowed=True) == {"/Users/"}
