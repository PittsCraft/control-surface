"""Acceptance of the overdue reminders, through the command line of the delivered project."""

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
    path = folder / name
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


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


# Ten days late and three days late for the first member, two days late for the second.
LATE = [
    loan("B1", "M1", "2026-03-10"),
    loan("B2", "M1", "2026-03-17"),
    loan("B3", "M2", "2026-03-18"),
]


class RemindTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_lines(self.data, "books.jsonl", BOOKS)
        write_lines(self.data, "members.jsonl", MEMBERS)

    def remind(self, today: str = TODAY) -> dict[str, list[str]]:
        """Run the command and return, by member, the other fields of each printed line."""
        result = lending(self.data, today, "remind")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
        return {row[0]: row[1:] for row in rows}

    def reminders(self) -> list[Record]:
        return [n for n in read_lines(self.data, "outbox.jsonl") if n["kind"] == "reminder"]

    def test_each_member_with_overdue_loans_gets_one_reminder_notice(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        self.remind()
        self.assertEqual(sorted(str(n["to"]) for n in self.reminders()), ["M1", "M2"])
        self.assertEqual({n["on"] for n in self.reminders()}, {TODAY})

    def test_prints_member_number_of_loans_and_total_fine(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        self.assertEqual(self.remind(), {"M1": ["2", "3.25"], "M2": ["1", "0.50"]})

    def test_the_notice_names_each_overdue_book_and_the_total_fine(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        self.remind()
        (text,) = [str(n["text"]) for n in self.reminders() if n["to"] == "M1"]
        self.assertIn("B1", text)
        self.assertIn("B2", text)
        self.assertIn("3.25", text)

    def test_the_books_that_are_not_overdue_are_left_out(self) -> None:
        loans = [loan("B1", "M1", "2026-03-10"), loan("B4", "M1", "2026-03-28")]
        write_lines(self.data, "loans.jsonl", loans)
        self.assertEqual(self.remind(), {"M1": ["1", "2.50"]})
        (notice,) = self.reminders()
        self.assertIn("B1", str(notice["text"]))
        self.assertNotIn("B4", str(notice["text"]))

    def test_a_member_with_nothing_overdue_gets_nothing(self) -> None:
        loans = [loan("B5", "M3", TODAY), loan("B6", "M3", "2026-03-28")]
        write_lines(self.data, "loans.jsonl", loans)
        self.assertEqual(self.remind(), {})
        self.assertEqual(self.reminders(), [])

    def test_a_returned_loan_is_not_reminded(self) -> None:
        loans = [loan("B1", "M1", "2026-03-01", returned="2026-03-12"), *LATE[2:]]
        write_lines(self.data, "loans.jsonl", loans)
        self.assertEqual(self.remind(), {"M2": ["1", "0.50"]})

    def test_no_member_is_reminded_twice_on_the_same_day(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        self.remind()
        self.assertEqual(self.remind(), {})
        self.assertEqual(len(self.reminders()), 2)

    def test_a_member_is_not_reminded_again_within_seven_days(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        self.remind("2026-03-20")
        self.assertEqual(self.remind("2026-03-26"), {})
        self.assertEqual(len(self.reminders()), 2)

    def test_a_member_is_reminded_again_seven_days_after_the_last_reminder(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        self.remind("2026-03-20")
        self.assertEqual(self.remind("2026-03-27"), {"M1": ["2", "6.75"], "M2": ["1", "2.25"]})
        self.assertEqual([n["on"] for n in self.reminders()].count("2026-03-27"), 2)

    def test_a_reminder_already_in_the_outbox_counts(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        earlier = {"to": "M1", "kind": "reminder", "text": "B1 is late.", "on": "2026-03-17"}
        write_lines(self.data, "outbox.jsonl", [earlier])
        self.assertEqual(self.remind(), {"M2": ["1", "0.50"]})

    def test_a_notice_of_another_kind_does_not_delay_the_reminder(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        other = {"to": "M1", "kind": "fine", "text": "Fine of 1.00.", "on": "2026-03-19"}
        write_lines(self.data, "outbox.jsonl", [other])
        self.assertEqual(sorted(self.remind()), ["M1", "M2"])

    def test_the_reminders_are_kept_in_the_outbox_and_nowhere_else(self) -> None:
        write_lines(self.data, "loans.jsonl", LATE)
        self.remind()
        self.assertEqual(read_lines(self.data, "loans.jsonl"), LATE)
        self.assertEqual(
            sorted(path.name for path in self.data.iterdir()),
            ["books.jsonl", "loans.jsonl", "members.jsonl", "outbox.jsonl"],
        )
