import tempfile
import unittest
from datetime import date
from pathlib import Path

from lending import loans, store
from lending.loans import Refused
from lending.reservations import (
    Reservation,
    borrow,
    cancel,
    expire,
    give_back,
    load_reservations,
    reserve,
)

BOOKS = [
    {"id": "B1", "title": "Emma", "author": "Austen", "price": "12.50"},
    {"id": "B2", "title": "Walden", "author": "Thoreau", "price": "9.00"},
]
MEMBERS = [
    {"id": f"M{number}", "name": f"Member {number}", "category": "student"}
    for number in range(1, 5)
]
MARCH_1 = date(2026, 3, 1)
MARCH_5 = date(2026, 3, 5)
MARCH_10 = date(2026, 3, 10)


class ReservationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        store.write(self.folder, "books.jsonl", BOOKS)
        store.write(self.folder, "members.jsonl", MEMBERS)
        loans.borrow(self.folder, "B1", "M1", MARCH_1)

    def holds(self) -> list[tuple[str, str]]:
        outbox = store.read(self.folder, "outbox.jsonl")
        return [(notice["to"], notice["on"]) for notice in outbox if notice["kind"] == "hold"]

    def test_a_reservation_joins_the_queue_of_a_book_on_loan(self) -> None:
        reserve(self.folder, "B1", "M2", MARCH_5)
        self.assertEqual(load_reservations(self.folder), [Reservation("B1", "M2", MARCH_5)])

    def test_reservations_a_rule_refuses(self) -> None:
        reserve(self.folder, "B1", "M2", MARCH_5)
        refused = [("B2", "M2"), ("B1", "M2"), ("B1", "M1"), ("B9", "M2"), ("B1", "M9")]
        for book, member in refused:
            with self.subTest(book=book, member=member), self.assertRaises(Refused):
                reserve(self.folder, book, member, MARCH_5)

    def test_a_returned_book_is_held_for_the_first_of_the_queue(self) -> None:
        reserve(self.folder, "B1", "M2", MARCH_5)
        reserve(self.folder, "B1", "M3", MARCH_5)
        give_back(self.folder, "B1", MARCH_10)
        self.assertEqual(self.holds(), [("M2", "2026-03-10")])
        with self.assertRaises(Refused):
            borrow(self.folder, "B1", "M3", MARCH_10)
        borrow(self.folder, "B1", "M2", MARCH_10)
        self.assertEqual(load_reservations(self.folder), [Reservation("B1", "M3", MARCH_5)])

    def test_cancelling_a_hold_passes_it_to_the_next(self) -> None:
        reserve(self.folder, "B1", "M2", MARCH_5)
        reserve(self.folder, "B1", "M3", MARCH_5)
        give_back(self.folder, "B1", MARCH_10)
        cancel(self.folder, "B1", "M2", date(2026, 3, 11))
        self.assertEqual(self.holds(), [("M2", "2026-03-10"), ("M3", "2026-03-11")])
        with self.assertRaises(Refused):
            cancel(self.folder, "B1", "M2", date(2026, 3, 11))

    def test_a_hold_expires_after_its_fifth_day(self) -> None:
        reserve(self.folder, "B1", "M2", MARCH_5)
        reserve(self.folder, "B1", "M3", MARCH_5)
        give_back(self.folder, "B1", MARCH_10)
        expire(self.folder, date(2026, 3, 15))
        self.assertEqual(self.holds(), [("M2", "2026-03-10")])
        expire(self.folder, date(2026, 3, 16))
        self.assertEqual(self.holds(), [("M2", "2026-03-10"), ("M3", "2026-03-16")])
        expire(self.folder, date(2026, 3, 22))
        self.assertEqual(load_reservations(self.folder), [])
        borrow(self.folder, "B1", "M4", date(2026, 3, 22))
