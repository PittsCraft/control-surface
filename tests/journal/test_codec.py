"""The strict JSONL codec: round trip, canonical form, and every way a line can be wrong."""

import json
from pathlib import Path

import pytest
from hypothesis import given
from journal_support import EVENTS, FIXTURES, journal_lines

from surface_status.events import EVENT_TYPES, PlanOpened, ReviewDone
from surface_status.journal import (
    JournalError,
    JournalLine,
    decode_line,
    encode_line,
)

AT = "2026-09-29T09:00:00Z"
DIGEST = "sha256:" + "a" * 64
OPENED = json.dumps({"v": 1, "at": AT, "event": "plan-opened", "slug": "feature"})


@given(journal_lines)
def test_encode_then_decode_is_the_identity_on_every_event(line: JournalLine) -> None:
    text = encode_line(line)
    assert "\n" not in text
    assert decode_line(text) == line
    assert encode_line(decode_line(text)) == text


def test_every_event_type_has_a_strategy() -> None:
    assert set(EVENTS) == set(EVENT_TYPES)


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.jsonl")), ids=lambda path: path.stem)
def test_a_golden_journal_re_encodes_byte_for_byte(path: Path) -> None:
    for row in path.read_text(encoding="utf-8").splitlines():
        assert encode_line(decode_line(row)) == row


def test_the_journal_keys_are_the_specs_names() -> None:
    line = JournalLine(AT, ReviewDone(pass_=2, report="r", defects=0, deviations=0, breaks=0))
    assert json.loads(encode_line(line))["pass"] == 2


def test_an_absent_proposal_is_left_out_of_the_line() -> None:
    line = JournalLine(AT, ReviewDone(pass_=1, report="r", defects=0, deviations=0, breaks=0))
    assert "proposal" not in encode_line(line)


def test_the_text_of_a_line_is_kept_readable_in_utf8() -> None:
    line = JournalLine(AT, PlanOpened(slug="é" + chr(0x2028)))
    assert "é" in encode_line(line)
    assert decode_line(encode_line(line)) == line


def _line(**changes: object) -> str:
    base: dict[str, object] = {"v": 1, "at": AT, "event": "plan-opened", "slug": "feature"}
    merged = {**base, **changes}
    return json.dumps({key: value for key, value in merged.items() if value is not ...})


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        (_line(v=2), "version"),
        (_line(v=True), "version"),
        (_line(v="1"), "version"),
        (_line(v=...), "version"),
        (_line(at="2026-09-29"), "at must"),
        (_line(at="2026-13-29T09:00:00Z"), "real date"),
        (_line(at="2026-09-29T09:00:00+00:00"), "at must"),
        (_line(at=...), "at must"),
        (_line(event="plan-closed"), "event"),
        (_line(event=3), "event"),
        (_line(extra=1), "unknown field extra"),
        (_line(slug=...), "lacks the field slug"),
        (_line(slug=3), "slug must be a text"),
        (_line(slug=None), "slug must be a text"),
        (
            '{"v": 1, "at": "2026-09-29T09:00:00Z", "event": "plan-opened", "slug": "\\ud800"}',
            "surrogate",
        ),
        ("[]", "expected a JSON object"),
        ("", "not valid JSON"),
        ("{", "not valid JSON"),
        (OPENED[:-1] + ', "slug": "again"}', "duplicate key"),
        (OPENED[:-1] + ', "x": NaN}', "NaN"),
    ],
)
def test_a_line_that_is_not_exactly_a_journal_line_is_refused(text: str, fragment: str) -> None:
    with pytest.raises(JournalError, match=fragment):
        decode_line(text)


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"event": "slice-done", "slice": True, "gates": "x", "slug": ...}, "slice must be"),
        ({"event": "slice-done", "slice": 0, "gates": "x", "slug": ...}, "at least 1"),
        ({"event": "slice-done", "slice": 1.0, "gates": "x", "slug": ...}, "slice must be"),
        ({"event": "slice-done", "slice": -1, "gates": "x", "slug": ...}, "slice must be"),
        ({"event": "interview-closed"}, "unknown field"),
        ({"event": "gates-run", "run": 1, "result": "green", "slug": ...}, "result must be"),
        ({"event": "gates-run", "run": 1, "result": 1, "slug": ...}, "result must be"),
        (
            {
                "event": "plan-drafted",
                "rev": 1,
                "overview": "abc",
                "plan": DIGEST,
                "slices": [1],
                "slug": ...,
            },
            "sha256",
        ),
        (
            {
                "event": "plan-drafted",
                "rev": 1,
                "overview": DIGEST.upper(),
                "plan": DIGEST,
                "slices": [1],
                "slug": ...,
            },
            "sha256",
        ),
        (
            {
                "event": "plan-drafted",
                "rev": 1,
                "overview": DIGEST,
                "plan": DIGEST,
                "slices": [1, 1],
                "slug": ...,
            },
            "duplicates",
        ),
        (
            {
                "event": "plan-drafted",
                "rev": 1,
                "overview": DIGEST,
                "plan": DIGEST,
                "slices": "1",
                "slug": ...,
            },
            "a list",
        ),
        (
            {
                "event": "plan-drafted",
                "rev": 1,
                "overview": DIGEST,
                "plan": DIGEST,
                "slices": [0],
                "slug": ...,
            },
            "at least 1",
        ),
        (
            {
                "event": "review-done",
                "pass": 1,
                "report": "r",
                "defects": 0,
                "deviations": 0,
                "breaks": 0,
                "proposal": None,
                "slug": ...,
            },
            "proposal must be",
        ),
    ],
)
def test_the_field_types_are_exact(changes: dict[str, object], fragment: str) -> None:
    with pytest.raises(JournalError, match=fragment):
        decode_line(_line(**changes))


@pytest.mark.parametrize(
    "text",
    [
        " " + OPENED,
        OPENED + " ",
        OPENED + "\r",
        OPENED.replace(": ", ":"),
        '{"at": "2026-09-29T09:00:00Z", "v": 1, "event": "plan-opened", "slug": "feature"}',
        OPENED.replace("feature", "\\u0066eature"),
    ],
)
def test_only_the_canonical_form_of_a_line_is_accepted(text: str) -> None:
    with pytest.raises(JournalError, match="canonical"):
        decode_line(text)


def test_an_event_the_decoder_would_refuse_is_never_encoded() -> None:
    with pytest.raises(JournalError):
        encode_line(JournalLine(AT, PlanOpened(slug="\ud800")))
    with pytest.raises(JournalError):
        encode_line(JournalLine("yesterday", PlanOpened(slug="feature")))
