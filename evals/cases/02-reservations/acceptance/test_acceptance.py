"""Acceptance of the reservations, through the command line of the delivered project.

A hold lasts 5 days: the rule the developer gives after reading the blueprint.
"""

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
RESERVED = "2026-03-05"
RETURNED = "2026-03-10"
NEXT_DAY = "2026-03-11"
LAST_DAY = "2026-03-15"  # the fifth day after the return
TOO_LATE = "2026-03-16"

BOOKS = [
    {"id": "B1", "title": "Wanted", "author": "Author", "price": "10.00"},
    {"id": "B2", "title": "On the shelf", "author": "Author", "price": "10.00"},
]
MEMBERS = [
    {"id": f"M{number}", "name": f"Member {number}", "category": "student"}
    for number in range(1, 5)
]
LOANS = [
    {"book": "B1", "member": "M1", "borrowed": "2026-03-01", "due": "2026-03-15", "returned": None}
]
LOAN_FIELDS = {"book", "member", "borrowed", "due", "returned"}


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


class ReservationsTest(unittest.TestCase):
    """The book B1 is on loan to M1; B2 is on the shelf."""

    def setUp(self) -> None:
        self.data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_lines(self.data, "books.jsonl", BOOKS)
        write_lines(self.data, "members.jsonl", MEMBERS)
        write_lines(self.data, "loans.jsonl", LOANS)

    def code(self, today: str, *command: str) -> int:
        return lending(self.data, today, *command).returncode

    def done(self, today: str, *command: str) -> None:
        result = lending(self.data, today, *command)
        self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")

    def queue(self, *members: str) -> None:
        for member in members:
            self.done(RESERVED, "reserve", "B1", member)

    def holds(self) -> list[tuple[object, object]]:
        """Return the member and the day of each hold notice, in the order of the outbox."""
        notices = read_lines(self.data, "outbox.jsonl")
        return [(n["to"], n["on"]) for n in notices if n["kind"] == "hold"]

    def test_a_book_on_the_shelf_cannot_be_reserved(self) -> None:
        self.assertEqual(self.code(RESERVED, "reserve", "B2", "M2"), 1)

    def test_a_member_cannot_reserve_the_same_book_twice(self) -> None:
        self.queue("M2")
        self.assertEqual(self.code(RESERVED, "reserve", "B1", "M2"), 1)

    def test_a_member_cannot_reserve_a_book_they_have_on_loan(self) -> None:
        self.assertEqual(self.code(RESERVED, "reserve", "B1", "M1"), 1)

    def test_a_return_holds_the_book_for_the_first_of_the_queue_and_notifies_them(self) -> None:
        self.queue("M2", "M3")
        self.done(RETURNED, "return", "B1")
        self.assertEqual(self.holds(), [("M2", RETURNED)])

    def test_only_the_holder_can_borrow_a_held_book(self) -> None:
        self.queue("M2", "M3")
        self.done(RETURNED, "return", "B1")
        self.assertEqual(self.code(NEXT_DAY, "borrow", "B1", "M3"), 1)
        self.assertEqual(self.code(NEXT_DAY, "borrow", "B1", "M4"), 1)
        self.done(NEXT_DAY, "borrow", "B1", "M2")
        self.assertEqual(lending(self.data, NEXT_DAY, "loans").stdout.split()[:2], ["B1", "M2"])

    def test_a_return_with_no_reservation_leaves_the_book_free(self) -> None:
        self.done(RETURNED, "return", "B1")
        self.assertEqual(self.holds(), [])
        self.done(NEXT_DAY, "borrow", "B1", "M4")

    def test_a_cancelled_reservation_leaves_the_queue(self) -> None:
        self.queue("M2", "M3")
        self.done(RESERVED, "cancel", "B1", "M2")
        self.done(RETURNED, "return", "B1")
        self.assertEqual(self.holds(), [("M3", RETURNED)])

    def test_cancelling_a_held_reservation_passes_the_hold_to_the_next_at_once(self) -> None:
        self.queue("M2", "M3")
        self.done(RETURNED, "return", "B1")
        self.done(NEXT_DAY, "cancel", "B1", "M2")
        self.assertEqual(self.holds(), [("M2", RETURNED), ("M3", NEXT_DAY)])
        self.assertEqual(self.code(NEXT_DAY, "borrow", "B1", "M2"), 1)
        self.done(NEXT_DAY, "borrow", "B1", "M3")

    def test_a_hold_can_be_picked_up_through_its_fifth_day(self) -> None:
        self.queue("M2", "M3")
        self.done(RETURNED, "return", "B1")
        self.done(LAST_DAY, "expire")
        self.assertEqual(self.holds(), [("M2", RETURNED)])
        self.done(LAST_DAY, "borrow", "B1", "M2")

    def test_expire_drops_a_hold_after_its_fifth_day_and_passes_it_to_the_next(self) -> None:
        self.queue("M2", "M3")
        self.done(RETURNED, "return", "B1")
        self.done(TOO_LATE, "expire")
        self.assertEqual(self.holds(), [("M2", RETURNED), ("M3", TOO_LATE)])
        self.assertEqual(self.code(TOO_LATE, "borrow", "B1", "M2"), 1)
        self.done(TOO_LATE, "borrow", "B1", "M3")

    def test_an_expired_hold_with_nobody_waiting_frees_the_book(self) -> None:
        self.queue("M2")
        self.done(RETURNED, "return", "B1")
        self.done(TOO_LATE, "expire")
        self.assertEqual(self.holds(), [("M2", RETURNED)])
        self.done(TOO_LATE, "borrow", "B1", "M4")

    def test_reservations_have_their_own_file_and_loans_keep_their_format(self) -> None:
        self.queue("M2")
        self.assertTrue((self.data / "reservations.jsonl").exists())
        self.done(RETURNED, "return", "B1")
        self.done(NEXT_DAY, "borrow", "B1", "M2")
        loans = read_lines(self.data, "loans.jsonl")
        self.assertEqual(len(loans), 2)
        for line in loans:
            self.assertEqual(set(line), LOAN_FIELDS)
