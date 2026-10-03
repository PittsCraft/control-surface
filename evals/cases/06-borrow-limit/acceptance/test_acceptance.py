"""Acceptance of the borrow limit, through the command line of the delivered project."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

Record = dict[str, Any]
PROJECT = Path(os.environ.get("LENDING_PROJECT", Path.cwd()))
TODAY = "2026-03-20"

BOOKS = [
    {"id": f"B{number}", "title": f"Title {number}", "author": "Author", "price": "10.00"}
    for number in range(1, 10)
]
MEMBERS = [
    {"id": "M1", "name": "First Member", "category": "student"},
    {"id": "M2", "name": "Second Member", "category": "student"},
    {"id": "M3", "name": "Third Member", "category": "staff"},
]


def write_lines(folder: Path, name: str, records: list[Record]) -> None:
    text = "".join(json.dumps(record) + "\n" for record in records)
    (folder / name).write_text(text, encoding="utf-8")


def read_lines(folder: Path, name: str) -> list[Record]:
    lines = (folder / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def loan(book: str, member: str, returned: str | None = None) -> Record:
    return {
        "book": book,
        "member": member,
        "borrowed": "2026-03-10",
        "due": "2026-03-24",
        "returned": returned,
    }


def lending(folder: Path, today: str, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lending", "--data", str(folder), "--today", today, *command],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )


class BorrowLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_lines(self.data, "books.jsonl", BOOKS)
        write_lines(self.data, "members.jsonl", MEMBERS)

    def holding(self, member: str, count: int) -> None:
        """Give the member the open loans of the books B1 to B<count>."""
        loans = [loan(f"B{number}", member) for number in range(1, count + 1)]
        write_lines(self.data, "loans.jsonl", loans)

    def borrow(self, book: str, member: str) -> subprocess.CompletedProcess[str]:
        return lending(self.data, TODAY, "borrow", book, member)

    def open_books(self, member: str) -> list[str]:
        result = lending(self.data, TODAY, "loans", "--member", member)
        self.assertEqual(result.returncode, 0, result.stderr)
        return sorted(line.split()[0] for line in result.stdout.splitlines() if line.strip())

    def test_a_student_with_two_open_loans_can_borrow_a_third(self) -> None:
        self.holding("M1", 2)
        result = self.borrow("B9", "M1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["B9", "M1", "due", "2026-04-03"])

    def test_a_student_with_three_open_loans_cannot_borrow_a_fourth(self) -> None:
        self.holding("M1", 3)
        self.assertEqual(self.borrow("B9", "M1").returncode, 1)

    def test_a_refused_borrow_records_no_loan(self) -> None:
        self.holding("M1", 3)
        self.borrow("B9", "M1")
        self.assertEqual(self.open_books("M1"), ["B1", "B2", "B3"])

    def test_staff_with_five_open_loans_can_borrow_a_sixth(self) -> None:
        self.holding("M3", 5)
        result = self.borrow("B9", "M3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.open_books("M3")), 6)

    def test_staff_with_six_open_loans_cannot_borrow_a_seventh(self) -> None:
        self.holding("M3", 6)
        self.assertEqual(self.borrow("B9", "M3").returncode, 1)
        self.assertEqual(len(self.open_books("M3")), 6)

    def test_returned_loans_do_not_count(self) -> None:
        loans = [loan(f"B{number}", "M1", returned="2026-03-15") for number in range(1, 6)]
        write_lines(self.data, "loans.jsonl", [*loans, loan("B6", "M1"), loan("B7", "M1")])
        result = self.borrow("B9", "M1")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_returning_a_book_frees_a_place_at_once(self) -> None:
        self.holding("M1", 3)
        self.assertEqual(self.borrow("B9", "M1").returncode, 1)
        self.assertEqual(lending(self.data, TODAY, "return", "B2").returncode, 0)
        result = self.borrow("B9", "M1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.open_books("M1"), ["B1", "B3", "B9"])

    def test_loans_already_above_the_limit_stay_as_they_are(self) -> None:
        self.holding("M1", 5)
        before = read_lines(self.data, "loans.jsonl")
        self.assertEqual(self.borrow("B9", "M1").returncode, 1)
        self.assertEqual(read_lines(self.data, "loans.jsonl"), before)
        self.assertEqual(self.open_books("M1"), ["B1", "B2", "B3", "B4", "B5"])

    def test_the_limit_is_counted_per_member(self) -> None:
        self.holding("M1", 3)
        result = self.borrow("B9", "M2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.open_books("M2"), ["B9"])
