"""The journal codec and its append-only writer (ADR 0012).

A line is `v`, `at`, `event`, then the own fields of the event in the order the dataclass declares
them, as JSON with the default separators. That form is the only one accepted: a line is decoded
strictly (version 1, no unknown or missing field, exact types) and must re-encode to the very same
text, so the format is deterministic and a hand edit that reformats a line is caught at replay.
"""

import json
import os
import re
from dataclasses import MISSING, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast, get_type_hints

from surface_status.events import EVENT_TYPES, Event, GateResult
from surface_status.strict_json import JsonError, loads_object

if TYPE_CHECKING:
    from collections.abc import Callable

VERSION = 1
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_HASH_KEYS = frozenset({"overview", "plan"})
_SLICE_KEYS = frozenset({"slice", "slices"})
_KINDS = {kind.name: kind for kind in EVENT_TYPES}


class JournalError(ValueError):
    """A journal that cannot be read or extended, with the line at fault when there is one."""

    def __init__(self, reason: str, line: int | None = None) -> None:
        super().__init__(reason if line is None else f"journal line {line}: {reason}")
        self.reason = reason
        self.line = line


@dataclass(frozen=True, slots=True)
class JournalLine:
    at: str  # UTC, `2026-09-29T09:00:00Z`
    event: Event


@dataclass(frozen=True, slots=True)
class _Field:
    attribute: str  # the dataclass attribute, `pass_`
    key: str  # the journal key, `pass`
    annotation: object
    required: bool


def _build_specs(kind: type[Event]) -> tuple[_Field, ...]:
    hints = get_type_hints(kind)
    return tuple(
        _Field(f.name, f.name.removesuffix("_"), hints[f.name], f.default is MISSING)
        for f in fields(kind)
    )


_SPECS = {kind: _build_specs(kind) for kind in EVENT_TYPES}


def _wrong(value: object, key: str, expected: str) -> JournalError:
    return JournalError(f"{key} must be {expected}, got {value!r}")


def _text(key: str, value: object) -> str:
    if not isinstance(value, str):
        raise _wrong(value, key, "a text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _wrong(value, key, "text without lone surrogates") from None
    if key in _HASH_KEYS and _HASH.fullmatch(value) is None:
        raise _wrong(value, key, "a `sha256:` hash in lower case")
    return value


def _whole(key: str, value: object, least: int) -> int:
    if type(value) is not int or value < least:
        raise _wrong(value, key, f"a whole number of at least {least}")
    return value


def _convert(field_: _Field, value: object) -> object:
    key, annotation = field_.key, field_.annotation
    least = 1 if key in _SLICE_KEYS else 0
    if annotation is int:
        return _whole(key, value, least)
    if annotation in {str, str | None}:
        return _text(key, value)
    if annotation is GateResult:
        try:
            return GateResult(_text(key, value))
        except ValueError:
            raise _wrong(value, key, "one of " + ", ".join(GateResult)) from None
    if annotation == tuple[int, ...]:
        if not isinstance(value, list):
            raise _wrong(value, key, "a list")
        listed = cast("list[object]", value)
        items = tuple(_whole(key, item, least) for item in listed)
        if len(set(items)) != len(items):
            raise _wrong(listed, key, "a list without duplicates")
        return items
    if annotation == tuple[str, ...] | None:
        if not isinstance(value, list):
            raise _wrong(value, key, "a list")
        return tuple(_text(key, item) for item in cast("list[object]", value))
    message = f"{key}: no codec for {annotation!r}"  # a new event field needs a rule here
    raise NotImplementedError(message)


def _decode(text: str) -> JournalLine:
    try:
        raw = loads_object(text)
    except JsonError as error:
        raise JournalError(str(error)) from error
    if type(raw.get("v")) is not int or raw["v"] != VERSION:
        raise _wrong(raw.get("v"), "v", f"the version {VERSION}")
    at = raw.get("at")
    if not isinstance(at, str) or _TIMESTAMP.fullmatch(at) is None:
        raise _wrong(at, "at", "a UTC date like 2026-09-29T09:00:00Z")
    try:
        datetime.strptime(at, TIMESTAMP_FORMAT)  # noqa: DTZ007 (the format fixes the zone, Z)
    except ValueError:
        raise _wrong(at, "at", "a real date") from None
    name = raw.get("event")
    if not isinstance(name, str) or name not in _KINDS:
        raise _wrong(name, "event", f"one of the {len(_KINDS)} events")
    kind = _KINDS[name]
    specs = _SPECS[kind]
    unknown = sorted(set(raw) - {"v", "at", "event"} - {spec.key for spec in specs})
    if unknown:
        message = f"unknown field {', '.join(unknown)} for {name}"
        raise JournalError(message)
    values: dict[str, object] = {}
    for spec in specs:
        if spec.key in raw:
            values[spec.attribute] = _convert(spec, raw[spec.key])
        elif spec.required:
            message = f"{name} lacks the field {spec.key}"
            raise JournalError(message)
    return JournalLine(at, cast("Callable[..., Event]", kind)(**values))


def _encode(line: JournalLine) -> str:
    event = line.event
    payload: dict[str, object] = {"v": VERSION, "at": line.at, "event": event.name}
    for spec in _SPECS[type(event)]:
        value = getattr(event, spec.attribute)
        if value is None and not spec.required:
            continue
        payload[spec.key] = (
            list(cast("tuple[object, ...]", value))
            if isinstance(value, tuple)
            else getattr(value, "value", value)
        )
    return json.dumps(payload, ensure_ascii=False)


def encode_line(line: JournalLine) -> str:
    """Return the canonical text of a line, without its newline.

    Refuses an event the decoder would refuse, since a line written to an append-only journal
    cannot be taken back.
    """
    text = _encode(line)
    if _decode(text) != line:
        message = "the event does not survive its own encoding"
        raise JournalError(message)
    return text


def decode_line(text: str) -> JournalLine:
    """Read one line, strictly, and only in canonical form."""
    line = _decode(text)
    if _encode(line) != text:
        message = "the line is not in canonical form"
        raise JournalError(message)
    return line


def parse_lines(data: bytes) -> list[JournalLine]:
    """Read the bytes of a whole journal. Empty bytes are an empty journal."""
    if not data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        message = f"the journal is not UTF-8: {error}"
        raise JournalError(message) from error
    rows = text.split("\n")
    if rows.pop() != "":
        message = "the journal does not end with a newline"
        raise JournalError(message, line=len(rows) + 1)
    lines: list[JournalLine] = []
    for number, row in enumerate(rows, start=1):
        try:
            lines.append(decode_line(row))
        except JournalError as error:
            raise JournalError(error.reason, line=number) from error
    return lines


def read_lines(path: Path) -> list[JournalLine]:
    """Read a whole journal. A missing or empty file is an empty journal."""
    try:
        return parse_lines(path.read_bytes())
    except FileNotFoundError:
        return []


def read_events(path: Path) -> list[Event]:
    return [line.event for line in read_lines(path)]


def parse_events(data: bytes) -> list[Event]:
    """Read the events of a journal held as bytes, such as a blob of another branch."""
    return [line.event for line in parse_lines(data)]


def append_line(path: Path, line: JournalLine) -> None:
    """Append one line, and nothing else, to a journal that ends with a newline (or is empty)."""
    data = (encode_line(line) + "\n").encode("utf-8")
    if not path.parent.is_dir():
        message = f"{path.parent} does not exist"
        raise JournalError(message)
    with path.open("ab+") as journal:
        size = journal.seek(0, os.SEEK_END)
        if size:
            journal.seek(size - 1)
            if journal.read(1) != b"\n":
                message = "the journal does not end with a newline, nothing was written"
                raise JournalError(message)
        journal.write(data)
        journal.flush()
        os.fsync(journal.fileno())
