"""Reading a journal file and appending to it."""

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from journal_support import FIXTURES, journal_lines

from surface_status.events import InterviewClosed, PlanOpened
from surface_status.journal import (
    JournalError,
    JournalLine,
    append_line,
    encode_line,
    read_events,
    read_lines,
)

AT = "2026-09-29T09:00:00Z"
OPENED = JournalLine(AT, PlanOpened(slug="feature"))
CLOSED = JournalLine(AT, InterviewClosed())


def test_a_missing_or_empty_journal_is_an_empty_one(tmp_path: Path) -> None:
    assert read_lines(tmp_path / "journal.jsonl") == []
    (tmp_path / "journal.jsonl").write_bytes(b"")
    assert read_lines(tmp_path / "journal.jsonl") == []


def test_a_golden_journal_reads_as_the_events_it_holds() -> None:
    events = read_events(FIXTURES / "abandon-from-interview.jsonl")
    assert [event.name for event in events] == ["plan-opened", "abandoned"]


def test_the_first_append_creates_the_journal(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    append_line(path, OPENED)
    assert path.read_bytes() == (encode_line(OPENED) + "\n").encode()


@given(st.lists(journal_lines, min_size=1, max_size=6))
def test_an_append_only_adds_its_own_line_after_the_existing_bytes(
    lines: list[JournalLine],
) -> None:
    import tempfile  # noqa: PLC0415 (one directory per example)

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "journal.jsonl"
        for line in lines:
            before = path.read_bytes() if path.exists() else b""
            append_line(path, line)
            after = path.read_bytes()
            assert after == before + (encode_line(line) + "\n").encode()
        assert read_lines(path) == lines


def test_a_journal_not_ending_with_a_newline_is_refused_and_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    torn = encode_line(OPENED).encode()
    path.write_bytes(torn)
    with pytest.raises(JournalError, match="newline"):
        append_line(path, CLOSED)
    assert path.read_bytes() == torn
    with pytest.raises(JournalError, match=r"line 1.*newline"):
        read_lines(path)


def test_an_append_beside_a_missing_folder_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(JournalError, match="does not exist"):
        append_line(tmp_path / "gone" / "journal.jsonl", OPENED)
    assert not (tmp_path / "gone").exists()


def test_the_line_at_fault_is_named(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    path.write_text(encode_line(OPENED) + "\n" + '{"v": 2}\n', encoding="utf-8")
    with pytest.raises(JournalError, match="journal line 2: v must be") as error:
        read_lines(path)
    assert error.value.line == 2


@pytest.mark.parametrize(
    "content",
    [
        b"\n",
        b"\n" + encode_line(OPENED).encode() + b"\n",
        encode_line(OPENED).encode() + b"\n\n",
        encode_line(OPENED).encode() + b"\r\n",
        b"\xff\xfe\n",
    ],
)
def test_blank_lines_crlf_and_bad_bytes_are_refused(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "journal.jsonl"
    path.write_bytes(content)
    with pytest.raises(JournalError):
        read_lines(path)
