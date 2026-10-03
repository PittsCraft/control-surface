"""The catalog: the books the library owns."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from lending import store

BOOKS = "books.jsonl"


@dataclass(frozen=True)
class Book:
    id: str
    title: str
    author: str
    price: Decimal | None  # None for an old book whose price nobody knows


def load_books(folder: Path) -> dict[str, Book]:
    """Return the books of the catalog by id, in the order of the file."""
    books = {}
    for record in store.read(folder, BOOKS):
        price = record.get("price")
        books[record["id"]] = Book(
            record["id"],
            record["title"],
            record["author"],
            None if price is None else Decimal(price),
        )
    return books
