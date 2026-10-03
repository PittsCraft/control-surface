"""The notices of the library to its members, queued in the outbox for the mailer."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lending import store

OUTBOX = "outbox.jsonl"


@dataclass(frozen=True)
class Notice:
    to: str  # the id of the member
    kind: str
    text: str
    on: date  # the day the notice is queued


def queue(folder: Path, notice: Notice) -> None:
    """Add a notice at the end of the outbox."""
    record = {
        "to": notice.to,
        "kind": notice.kind,
        "text": notice.text,
        "on": notice.on.isoformat(),
    }
    store.append(folder, OUTBOX, record)


def load_notices(folder: Path) -> list[Notice]:
    """Return the notices of the outbox, in the order they were queued."""
    return [
        Notice(record["to"], record["kind"], record["text"], date.fromisoformat(record["on"]))
        for record in store.read(folder, OUTBOX)
    ]
