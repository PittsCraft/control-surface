"""Acceptance of the overdue list, through the command line of the delivered project."""

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
    for number in range(1, 6)
]
MEMBERS = [
    {"id": "M1", "name": "First Member", "category": "student"},
    {"id": "M2", "name": "Second Member", "category": "staff"},
]


def write_lines(folder: Path, name: str, records: list[Record]) -> None:
    text = "".join(json.dumps(record) + "\n" for record in records)
    (folder / name).write_text(text, encoding="utf-8")


def loan(book: str, member: str, due: str, returned: str | None = None) -> Record:
    return {
        "book": book,
        "member": member,
        "borrowed": "2026-01-05",
        "due": due,
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


class OverdueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_lines(self.data, "books.jsonl", BOOKS)
        write_lines(self.data, "members.jsonl", MEMBERS)

    def overdue(self, *loans: Record) -> list[list[str]]:
        """Run the command on these loans and return the fields of each printed line."""
        write_lines(self.data, "loans.jsonl", list(loans))
        result = lending(self.data, TODAY, "overdue")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.split() for line in result.stdout.splitlines() if line.strip()]

    def test_prints_book_member_due_date_and_days_late(self) -> None:
        self.assertEqual(
            self.overdue(loan("B1", "M2", "2026-03-15")), [["B1", "M2", "2026-03-15", "5"]]
        )

    def test_days_late_count_from_the_day_after_the_due_date(self) -> None:
        self.assertEqual(self.overdue(loan("B1", "M1", "2026-03-19"))[0][3], "1")

    def test_the_most_days_late_comes_first(self) -> None:
        rows = self.overdue(
            loan("B1", "M1", "2026-03-18"),
            loan("B2", "M2", "2026-02-01"),
            loan("B3", "M1", "2026-03-10"),
        )
        self.assertEqual([row[0] for row in rows], ["B2", "B3", "B1"])
        self.assertEqual([row[3] for row in rows], ["47", "10", "2"])

    def test_ties_in_days_late_are_ordered_by_book_id(self) -> None:
        rows = self.overdue(
            loan("B3", "M1", "2026-03-10"),
            loan("B1", "M2", "2026-03-10"),
            loan("B4", "M1", "2026-03-01"),
            loan("B2", "M1", "2026-03-10"),
        )
        self.assertEqual([row[0] for row in rows], ["B4", "B1", "B2", "B3"])

    def test_a_loan_due_today_is_not_overdue(self) -> None:
        rows = self.overdue(loan("B1", "M1", TODAY), loan("B2", "M1", "2026-03-19"))
        self.assertEqual([row[0] for row in rows], ["B2"])

    def test_a_loan_not_yet_due_is_not_listed(self) -> None:
        rows = self.overdue(loan("B1", "M1", "2026-03-25"), loan("B2", "M1", "2026-03-19"))
        self.assertEqual([row[0] for row in rows], ["B2"])

    def test_a_returned_loan_is_not_listed_even_when_it_came_back_late(self) -> None:
        rows = self.overdue(
            loan("B1", "M1", "2026-03-01", returned="2026-03-12"),
            loan("B2", "M1", "2026-03-19"),
        )
        self.assertEqual([row[0] for row in rows], ["B2"])

    def test_nothing_overdue_prints_nothing_and_exits_zero(self) -> None:
        self.assertEqual(self.overdue(loan("B1", "M1", "2026-03-25")), [])

    def test_no_loans_file_prints_nothing_and_exits_zero(self) -> None:
        result = lending(self.data, TODAY, "overdue")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, ""))

    def test_the_command_changes_no_file(self) -> None:
        self.overdue(loan("B1", "M1", "2026-03-01"), loan("B2", "M2", "2026-03-25"))
        self.assertEqual(
            sorted(path.name for path in self.data.iterdir()),
            ["books.jsonl", "loans.jsonl", "members.jsonl"],
        )
