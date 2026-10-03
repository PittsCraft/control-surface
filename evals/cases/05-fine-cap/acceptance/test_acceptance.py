"""Acceptance of the grace days and the cap of a fine, through the command line."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import Any

Record = dict[str, Any]
PROJECT = Path(os.environ.get("LENDING_PROJECT", Path.cwd()))
DUE = date(2026, 3, 10)

BOOKS = [
    {"id": "B1", "title": "Priced", "author": "Author", "price": "12.50"},
    {"id": "B2", "title": "Cheap", "author": "Author", "price": "3.50"},
    {"id": "B3", "title": "Old", "author": "Author"},
    {"id": "B4", "title": "Typed short", "author": "Author", "price": "3.5"},
]
MEMBERS = [{"id": "M1", "name": "First Member", "category": "student"}]


def write_lines(folder: Path, name: str, records: list[Record]) -> None:
    text = "".join(json.dumps(record) + "\n" for record in records)
    (folder / name).write_text(text, encoding="utf-8")


def read_lines(folder: Path, name: str) -> list[Record]:
    path = folder / name
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def lending(folder: Path, today: str, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lending", "--data", str(folder), "--today", today, *command],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )


class FineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_lines(self.data, "books.jsonl", BOOKS)
        write_lines(self.data, "members.jsonl", MEMBERS)

    def late(self, book: str, days: int, command: str) -> str:
        """Run a command on a loan of the book that is this many days late, return its output."""
        record = {
            "book": book,
            "member": "M1",
            "borrowed": (DUE - timedelta(days=14)).isoformat(),
            "due": DUE.isoformat(),
            "returned": None,
        }
        write_lines(self.data, "loans.jsonl", [record])
        today = (DUE + timedelta(days=days)).isoformat()
        result = lending(self.data, today, command, book)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def fine(self, book: str, days: int) -> str:
        return self.late(book, days, "fine")

    def returned(self, book: str, days: int) -> str:
        """Return the amount at the end of the line `<book> returned, fine <amount>`."""
        return self.late(book, days, "return").split()[-1]

    def fine_notices(self) -> list[Record]:
        return [n for n in read_lines(self.data, "outbox.jsonl") if n["kind"] == "fine"]

    def test_no_fine_for_the_first_two_days_late(self) -> None:
        self.assertEqual(self.fine("B1", 1), "0.00")
        self.assertEqual(self.fine("B1", 2), "0.00")

    def test_a_loan_three_days_late_owes_one_day(self) -> None:
        self.assertEqual(self.fine("B1", 3), "0.25")

    def test_each_day_after_the_grace_costs_a_quarter(self) -> None:
        self.assertEqual(self.fine("B1", 10), "2.00")

    def test_a_fine_never_exceeds_the_price_of_the_book(self) -> None:
        self.assertEqual(self.fine("B2", 16), "3.50")
        self.assertEqual(self.fine("B2", 30), "3.50")

    def test_a_fine_below_the_price_is_not_capped(self) -> None:
        self.assertEqual(self.fine("B2", 15), "3.25")

    def test_a_book_with_no_known_price_is_not_capped(self) -> None:
        self.assertEqual(self.fine("B3", 100), "24.50")

    def test_a_capped_fine_keeps_two_decimals(self) -> None:
        self.assertEqual(self.fine("B4", 30), "3.50")

    def test_return_prints_the_fine_after_the_grace(self) -> None:
        self.assertEqual(self.returned("B1", 2), "0.00")
        self.assertEqual(self.returned("B1", 3), "0.25")

    def test_return_caps_the_fine_at_the_price(self) -> None:
        self.assertEqual(self.returned("B2", 30), "3.50")

    def test_a_return_within_the_grace_queues_no_fine_notice(self) -> None:
        self.returned("B1", 2)
        self.assertEqual(self.fine_notices(), [])

    def test_the_fine_notice_of_a_return_carries_the_capped_amount(self) -> None:
        self.returned("B2", 30)
        (notice,) = self.fine_notices()
        self.assertIn("3.50", str(notice["text"]))
        self.assertNotIn("7.00", str(notice["text"]))
