import tempfile
import unittest
from datetime import date
from pathlib import Path

from lending import store
from lending.loans import (
    Loan,
    Refused,
    borrow,
    give_back,
    load_loans,
    open_loan_of,
    open_loans,
    overdue,
    save_loans,
)

BOOKS = [
    {"id": "B1", "title": "Emma", "author": "Austen", "price": "12.50"},
    {"id": "B2", "title": "Walden", "author": "Thoreau", "price": "9.00"},
]
MEMBERS = [
    {"id": "M1", "name": "Avery Lane", "category": "student"},
    {"id": "M2", "name": "Robin Hale", "category": "staff"},
]
MARCH_1 = date(2026, 3, 1)
MARCH_15 = date(2026, 3, 15)


class BorrowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        store.write(self.folder, "books.jsonl", BOOKS)
        store.write(self.folder, "members.jsonl", MEMBERS)

    def test_a_loan_lasts_fourteen_days(self) -> None:
        loan = borrow(self.folder, "B1", "M1", MARCH_1)
        self.assertEqual(loan, Loan("B1", "M1", MARCH_1, MARCH_15))
        self.assertEqual(load_loans(self.folder), [loan])

    def test_a_loan_line_has_five_fields(self) -> None:
        borrow(self.folder, "B1", "M1", MARCH_1)
        line = {
            "book": "B1",
            "member": "M1",
            "borrowed": "2026-03-01",
            "due": "2026-03-15",
            "returned": None,
        }
        self.assertEqual(store.read(self.folder, "loans.jsonl"), [line])

    def test_a_book_on_loan_cannot_be_borrowed(self) -> None:
        borrow(self.folder, "B1", "M1", MARCH_1)
        with self.assertRaises(Refused):
            borrow(self.folder, "B1", "M2", MARCH_1)

    def test_an_unknown_book_or_member_is_refused(self) -> None:
        with self.assertRaises(Refused):
            borrow(self.folder, "B9", "M1", MARCH_1)
        with self.assertRaises(Refused):
            borrow(self.folder, "B1", "M9", MARCH_1)
        self.assertEqual(load_loans(self.folder), [])

    def hold(self, member: str, count: int) -> None:
        loans = [Loan(f"X{number}", member, MARCH_1, MARCH_15) for number in range(count)]
        save_loans(self.folder, loans)

    def test_a_student_holds_at_most_three_books(self) -> None:
        self.hold("M1", 2)
        borrow(self.folder, "B1", "M1", MARCH_1)
        with self.assertRaises(Refused):
            borrow(self.folder, "B2", "M1", MARCH_1)
        self.assertEqual(len(load_loans(self.folder)), 3)

    def test_staff_hold_at_most_six_books(self) -> None:
        self.hold("M2", 5)
        borrow(self.folder, "B1", "M2", MARCH_1)
        with self.assertRaises(Refused):
            borrow(self.folder, "B2", "M2", MARCH_1)

    def test_a_returned_book_frees_a_place(self) -> None:
        self.hold("M1", 2)
        borrow(self.folder, "B1", "M1", MARCH_1)
        give_back(self.folder, "B1", MARCH_15)
        borrow(self.folder, "B2", "M1", MARCH_15)
        self.assertEqual(len(open_loans(load_loans(self.folder), "M1")), 3)

    def test_give_back_sets_the_return_date(self) -> None:
        borrow(self.folder, "B1", "M1", MARCH_1)
        returned = give_back(self.folder, "B1", date(2026, 3, 10))
        self.assertEqual(returned.returned, date(2026, 3, 10))
        self.assertEqual(load_loans(self.folder), [returned])

    def test_a_book_on_the_shelf_cannot_be_given_back(self) -> None:
        with self.assertRaises(Refused):
            give_back(self.folder, "B1", MARCH_1)

    def test_a_returned_book_can_be_borrowed_again(self) -> None:
        borrow(self.folder, "B1", "M1", MARCH_1)
        give_back(self.folder, "B1", date(2026, 3, 10))
        again = borrow(self.folder, "B1", "M2", date(2026, 3, 10))
        self.assertEqual(open_loans(load_loans(self.folder)), [again])


class OpenLoansTest(unittest.TestCase):
    def setUp(self) -> None:
        self.back = Loan("B1", "M1", MARCH_1, MARCH_15, returned=date(2026, 3, 20))
        self.late = Loan("B2", "M1", MARCH_1, MARCH_15)
        self.other = Loan("B3", "M2", MARCH_15, date(2026, 3, 29))
        self.loans = [self.back, self.late, self.other]

    def test_open_loans_leave_out_the_returned_ones(self) -> None:
        self.assertEqual(open_loans(self.loans), [self.late, self.other])
        self.assertEqual(open_loans(self.loans, "M2"), [self.other])
        self.assertEqual(open_loan_of(self.loans, "B2"), self.late)
        self.assertIsNone(open_loan_of(self.loans, "B1"))

    def test_a_loan_due_today_is_not_overdue(self) -> None:
        self.assertEqual(overdue(self.loans, MARCH_15), [])
        self.assertEqual(overdue(self.loans, date(2026, 3, 16)), [self.late])
