"""Acceptance of the suspension of members who owe too much, through the command line."""

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
TODAY = date(2026, 6, 1)

BOOKS = [
    {"id": f"B{number}", "title": f"Title {number}", "author": "Author", "price": "40.00"}
    for number in range(1, 7)
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


def late(book: str, member: str, days: int, *, returned: bool = False) -> Record:
    """Return a loan line this many days late today: each day late costs 0.25."""
    due = TODAY - timedelta(days=days)
    return {
        "book": book,
        "member": member,
        "borrowed": (due - timedelta(days=14)).isoformat(),
        "due": due.isoformat(),
        "returned": TODAY.isoformat() if returned else None,
    }


def lending(folder: Path, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "lending",
            "--data",
            str(folder),
            "--today",
            TODAY.isoformat(),
            *command,
        ],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )


class SuspensionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_lines(self.data, "books.jsonl", BOOKS)
        write_lines(self.data, "members.jsonl", MEMBERS)

    def loans(self, *loans: Record) -> None:
        write_lines(self.data, "loans.jsonl", list(loans))

    def borrow(self, book: str, member: str) -> int:
        return lending(self.data, "borrow", book, member).returncode

    def open_books(self) -> list[str]:
        result = lending(self.data, "loans")
        self.assertEqual(result.returncode, 0, result.stderr)
        return sorted(line.split()[0] for line in result.stdout.splitlines() if line.strip())

    def owed(self, member: str) -> str:
        result = lending(self.data, "owed", member)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_a_member_owing_more_than_ten_cannot_borrow(self) -> None:
        self.loans(late("B1", "M1", 41))
        self.assertEqual(self.borrow("B6", "M1"), 1)

    def test_a_refused_borrow_records_no_loan(self) -> None:
        self.loans(late("B1", "M1", 41))
        self.borrow("B6", "M1")
        self.assertEqual(self.open_books(), ["B1"])

    def test_a_member_owing_exactly_ten_can_still_borrow(self) -> None:
        self.loans(late("B1", "M1", 40))
        self.assertEqual(self.borrow("B6", "M1"), 0)
        self.assertEqual(self.open_books(), ["B1", "B6"])

    def test_what_is_owed_adds_up_the_open_loans_of_the_member(self) -> None:
        self.loans(late("B1", "M1", 20), late("B2", "M1", 21))
        self.assertEqual(self.borrow("B6", "M1"), 1)

    def test_staff_are_suspended_like_students(self) -> None:
        self.loans(late("B1", "M3", 41))
        self.assertEqual(self.borrow("B6", "M3"), 1)

    def test_returned_loans_no_longer_count(self) -> None:
        self.loans(late("B1", "M1", 100, returned=True), late("B2", "M1", 40))
        self.assertEqual(self.borrow("B6", "M1"), 0)

    def test_returning_the_late_book_lifts_the_suspension(self) -> None:
        self.loans(late("B1", "M1", 41))
        self.assertEqual(self.borrow("B6", "M1"), 1)
        self.assertEqual(lending(self.data, "return", "B1").returncode, 0)
        self.assertEqual(self.borrow("B6", "M1"), 0)

    def test_a_suspended_member_does_not_stop_another_one(self) -> None:
        self.loans(late("B1", "M1", 41), late("B2", "M2", 3))
        self.assertEqual(self.borrow("B6", "M2"), 0)

    def test_owed_prints_the_amount_with_two_decimals(self) -> None:
        self.loans(late("B1", "M1", 20), late("B2", "M1", 21), late("B3", "M2", 8))
        self.assertEqual(self.owed("M1"), "10.25")
        self.assertEqual(self.owed("M2"), "2.00")

    def test_owed_prints_zero_for_a_member_who_owes_nothing(self) -> None:
        self.loans(late("B1", "M1", 0))
        self.assertEqual(self.owed("M1"), "0.00")
        self.assertEqual(self.owed("M2"), "0.00")

    def test_owed_leaves_out_the_returned_loans(self) -> None:
        self.loans(late("B1", "M1", 100, returned=True), late("B2", "M1", 4))
        self.assertEqual(self.owed("M1"), "1.00")

    def test_nothing_is_stored_about_what_a_member_owes(self) -> None:
        self.loans(late("B1", "M1", 41))
        before = read_lines(self.data, "loans.jsonl")
        self.borrow("B6", "M1")
        self.owed("M1")
        self.assertEqual(read_lines(self.data, "loans.jsonl"), before)
        self.assertEqual(
            sorted(path.name for path in self.data.iterdir()),
            ["books.jsonl", "loans.jsonl", "members.jsonl"],
        )
