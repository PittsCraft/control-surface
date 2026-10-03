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
