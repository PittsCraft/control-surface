"""The data directory: JSON Lines files, one JSON object per line.

The only module that reads and writes files. A missing file reads as empty.
"""

import json
from pathlib import Path
from typing import Any

Record = dict[str, Any]


def read(folder: Path, name: str) -> list[Record]:
    """Return the records of a file of the data directory, in the order of its lines."""
    path = folder / name
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def write(folder: Path, name: str, records: list[Record]) -> None:
    """Replace a file of the data directory with these records, one per line."""
    folder.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(record) + "\n" for record in records)
    (folder / name).write_text(text, encoding="utf-8")


def append(folder: Path, name: str, record: Record) -> None:
    """Add one record at the end of a file of the data directory."""
    write(folder, name, [*read(folder, name), record])
