"""The members: the people who borrow from the library."""

from dataclasses import dataclass
from pathlib import Path

from lending import store

MEMBERS = "members.jsonl"


@dataclass(frozen=True)
class Member:
    id: str
    name: str
    category: str  # "student" or "staff"


def load_members(folder: Path) -> dict[str, Member]:
    """Return the members by id, in the order of the file."""
    return {
        record["id"]: Member(record["id"], record["name"], record["category"])
        for record in store.read(folder, MEMBERS)
    }
