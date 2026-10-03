import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from lending import store
from lending.catalog import Book, load_books


class LoadBooksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_reads_the_price_as_a_decimal(self) -> None:
        record = {"id": "B1", "title": "Emma", "author": "Austen", "price": "12.50"}
        store.write(self.folder, "books.jsonl", [record])
        self.assertEqual(
            load_books(self.folder), {"B1": Book("B1", "Emma", "Austen", Decimal("12.50"))}
        )

    def test_a_book_without_price_has_none(self) -> None:
        store.write(self.folder, "books.jsonl", [{"id": "B4", "title": "Herbal", "author": "?"}])
        self.assertIsNone(load_books(self.folder)["B4"].price)
