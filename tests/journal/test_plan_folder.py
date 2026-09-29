"""Paths, numbering, hashing, slice markers and the gates block of the plan folder."""

import re
import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from journal_support import EVENTS, new_folder, write

from surface_status.events import EVENT_TYPES, GateResult, GatesRun, PlanApproved, ReviewDone
from surface_status.plan_folder import (
    GatesBlockError,
    PlanFolderError,
    SliceMarkerError,
    cited_files,
    content_hash,
    parse_gates,
    parse_slice_markers,
)

# Hashes: CRLF read as LF (ARCHITECTURE.md, Journal and state)


def test_the_same_text_hashes_alike_with_lf_or_crlf_endings() -> None:
    assert content_hash(b"a\nb\n") == content_hash(b"a\r\nb\r\n") == content_hash(b"a\nb\r\n")


@given(st.text().map(lambda text: text.replace("\r", "")), st.lists(st.booleans()))
def test_any_mix_of_endings_hashes_like_the_lf_text(text: str, choices: list[bool]) -> None:
    lf = text.encode()
    pieces = text.split("\n")
    mixed = pieces[0]
    for index, piece in enumerate(pieces[1:]):
        crlf = choices[index] if index < len(choices) else False
        mixed += ("\r\n" if crlf else "\n") + piece
    assert content_hash(mixed.encode()) == content_hash(lf)


def test_a_hash_has_the_documented_shape_and_tells_contents_apart() -> None:
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", content_hash(b""))
    assert content_hash(b"a") != content_hash(b"b")
    assert content_hash(b"a\rb") != content_hash(b"a\nb")  # only CRLF is normalized


def test_a_file_hash_reads_the_file_and_is_none_when_it_is_missing(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    folder.overview.write_bytes(b"x\r\ny\r\n")
    assert folder.overview_hash() == content_hash(b"x\ny\n")
    folder.overview.unlink()
    assert folder.overview_hash() is None
    assert folder.file_hash("gates") is None  # a folder is not a file


# Slice markers

_prose = st.lists(
    st.text(max_size=30).filter(lambda line: "slice:" not in line and "\r" not in line),
    max_size=8,
)


@given(
    st.lists(st.integers(1, 999), unique=True, max_size=6),
    st.lists(_prose, min_size=7, max_size=7),
    st.sampled_from(["\n", "\r\n"]),
)
def test_the_marker_list_does_not_depend_on_the_prose_or_the_language_around(
    numbers: list[int], prose: list[list[str]], newline: str
) -> None:
    lines: list[str] = []
    for index, number in enumerate(numbers):
        lines += [*prose[index], f"<!-- slice:{number} -->", "## Tranche : titre"]
    lines += prose[-1]
    assert parse_slice_markers(newline.join(lines)) == tuple(numbers)


@given(st.lists(st.integers(1, 99), unique=True, min_size=1, max_size=6), st.data())
def test_a_duplicated_number_is_an_error(numbers: list[int], data: st.DataObject) -> None:
    repeated = data.draw(st.sampled_from(numbers))
    position = data.draw(st.integers(0, len(numbers)))
    listed = [*numbers[:position], repeated, *numbers[position:]]
    text = "\n".join(f"<!-- slice:{n} -->" for n in listed)
    with pytest.raises(SliceMarkerError, match="declared twice"):
        parse_slice_markers(text)


@pytest.mark.parametrize("raw", ["0", "03", "-1", "x", "1.5", ""])
def test_a_marker_without_a_positive_number_is_an_error(raw: str) -> None:
    with pytest.raises(SliceMarkerError, match="line 2"):
        parse_slice_markers(f"prose\n<!-- slice:{raw} -->\n")


def test_only_a_whole_line_marker_counts() -> None:
    text = (
        "Quote: `<!-- slice:9 -->` inline\n"
        "  <!-- slice:8 -->\n"
        "text <!-- slice:7 -->\n"
        "<!--slice:1-->\n"
        "<!--   slice: 2   -->\n"
        "<!-- other:3 -->\n"
    )
    assert parse_slice_markers(text) == (1, 2)


def test_the_marker_order_is_the_order_of_appearance() -> None:
    assert parse_slice_markers("<!-- slice:5 -->\n<!-- slice:2 -->\n") == (5, 2)


def test_the_folder_reads_the_slices_of_its_plan(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    assert folder.declared_slices() == (1, 2)
    folder.plan.unlink()
    with pytest.raises(PlanFolderError, match=r"plan\.md cannot be read"):
        folder.declared_slices()


# The gates block


@given(
    st.lists(
        st.text(alphabet=st.characters(exclude_characters="\r\n`"), min_size=1, max_size=20).filter(
            lambda line: bool(line.strip())
        ),
        max_size=5,
    ),
    st.sampled_from(["\n", "\r\n"]),
)
def test_the_gates_are_the_lines_of_the_block_in_order(commands: list[str], newline: str) -> None:
    lines = ["## Portes", "Les commandes :", "```gates", *commands, "```", "", "fin"]
    expected = tuple(command.strip() for command in commands)
    assert parse_gates(newline.join(lines)) == expected


def test_blank_lines_are_skipped_and_commands_stripped() -> None:
    text = "```gates\n\n  make test  \n\t\nmake lint && make types\n```\n"
    assert parse_gates(text) == ("make test", "make lint && make types")


def test_an_empty_block_names_no_gate_and_a_missing_one_names_nothing() -> None:
    assert parse_gates("prose\n```gates\n```\n") == ()
    assert parse_gates("prose\n```sh\nmake test\n```\n") is None
    assert parse_gates("  ```gates\nmake\n  ```\n") is None  # the fence starts at column 0


def test_a_second_block_or_an_unclosed_one_is_an_error() -> None:
    with pytest.raises(GatesBlockError, match="line 4: a second gates block"):
        parse_gates("```gates\na\n```\n```gates\nb\n```\n")
    with pytest.raises(GatesBlockError, match="line 2: the gates block is not closed"):
        parse_gates("prose\n```gates\nmake test\n")


def test_the_folder_reads_the_gates_of_its_plan(tmp_path: Path) -> None:
    folder = new_folder(tmp_path, gates=("make test", "make lint"))
    assert folder.declared_gates() == ("make test", "make lint")
    folder.plan.unlink()
    with pytest.raises(PlanFolderError, match=r"plan\.md cannot be read"):
        folder.declared_gates()


# Numbering


def test_numbers_start_at_one_and_follow_the_highest_existing_report(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    assert folder.next_check(1) == "checks/rev-01-01.md"
    assert folder.next_review() == "reviews/pass-01.md"
    assert folder.next_suspicion() == "reviews/suspicion-01.md"
    assert folder.next_gate_run() == 1
    assert folder.next_plan_change() == "plan-changes/01.md"
    write(folder, "checks/rev-01-01.md")
    write(folder, "checks/rev-01-02.md")
    write(folder, "checks/rev-02-01.md")
    write(folder, "reviews/pass-03.md")
    write(folder, "reviews/suspicion-01.md")
    write(folder, "gates/run-07.txt")
    write(folder, "plan-changes/02.md")
    assert folder.next_check(1) == "checks/rev-01-03.md"
    assert folder.next_check(2) == "checks/rev-02-02.md"
    assert folder.next_check(3) == "checks/rev-03-01.md"
    assert folder.next_review() == "reviews/pass-04.md"
    assert folder.next_suspicion() == "reviews/suspicion-02.md"
    assert folder.next_gate_run() == 8
    assert folder.next_plan_change() == "plan-changes/03.md"


def test_files_that_do_not_follow_the_naming_are_ignored_by_the_numbering(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    write(folder, "reviews/pass-x.md")
    write(folder, "reviews/notes.md")
    write(folder, "reviews/pass-02.md.bak")
    write(folder, "gates/run-2.txt.orig")
    assert folder.next_review() == "reviews/pass-01.md"
    assert folder.next_gate_run() == 1


def test_numbers_go_past_two_digits_without_a_clash(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    write(folder, "reviews/pass-99.md")
    assert folder.next_review() == "reviews/pass-100.md"
    write(folder, "reviews/pass-100.md")
    assert folder.next_review() == "reviews/pass-101.md"


# Cited files


def test_every_event_type_has_a_rule_for_the_files_it_cites() -> None:
    for kind in EVENT_TYPES:
        assert kind in EVENTS
    assert cited_files(PlanApproved(rev=1, overview="x")) == ("overview.md",)
    assert cited_files(GatesRun(run=3, result=GateResult.PASS)) == ("gates/run-03.txt",)
    review = ReviewDone(pass_=1, report="r.md", defects=0, deviations=0, breaks=1, proposal="p.md")
    assert cited_files(review) == ("r.md", "p.md")


@pytest.mark.parametrize(
    "name",
    ["", "/etc/passwd", "../x", "a/../../x", "a//b", "./a", "a/", "a\\b", "C:\\x", "."],
)
def test_a_name_leaving_the_folder_is_not_a_path_of_it(tmp_path: Path, name: str) -> None:
    folder = new_folder(tmp_path)
    with pytest.raises(PlanFolderError):
        folder.path(name)
    assert not folder.is_file(name)


def test_a_cited_file_must_be_a_regular_file_inside_the_folder(tmp_path: Path) -> None:
    folder = new_folder(tmp_path)
    (tmp_path / "outside.md").write_text("x", encoding="utf-8")
    (folder.root / "reviews").mkdir()
    (folder.root / "reviews" / "link.md").symlink_to(tmp_path / "outside.md")
    write(folder, "reviews/pass-01.md")
    assert folder.is_file("reviews/pass-01.md")
    assert not folder.is_file("reviews/link.md")  # a link out of the folder
    assert not folder.is_file("reviews")  # a directory
    assert not folder.is_file("reviews/pass-02.md")


def test_the_temporary_folder_helper_leaves_no_trace() -> None:
    with tempfile.TemporaryDirectory() as directory:
        assert new_folder(Path(directory)).name == "2026-09-29-feature"
