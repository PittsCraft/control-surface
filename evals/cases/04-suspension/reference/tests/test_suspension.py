import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from lending import store
from lending.loans import Loan, Refused, save_loans
from lending.suspension import check, owed

TODAY = date(2026, 6, 1)
MEMBERS = [
    {"id": "M1", "name": "Avery Lane", "category": "student"},
    {"id": "M2", "name": "Robin Hale", "category": "staff"},
]


def late(book: str, member: str, days: int, returned: date | None = None) -> Loan:
    due = TODAY - timedelta(days=days)
    return Loan(book, member, due - timedelta(days=14), due, returned)


class SuspensionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        store.write(self.folder, "members.jsonl", MEMBERS)

    def test_owed_is_the_sum_of_the_fines_of_the_open_loans(self) -> None:
        loans = [late("B1", "M1", 20), late("B2", "M1", 21), late("B3", "M1", 90, TODAY)]
        save_loans(self.folder, [*loans, late("B4", "M2", 8)])
        self.assertEqual(owed(self.folder, "M1", TODAY), Decimal("10.25"))
        self.assertEqual(owed(self.folder, "M2", TODAY), Decimal("2.00"))

    def test_an_unknown_member_is_refused(self) -> None:
        with self.assertRaises(Refused):
            owed(self.folder, "M9", TODAY)

    def test_a_member_owing_exactly_the_limit_passes(self) -> None:
        save_loans(self.folder, [late("B1", "M1", 40)])
        check(self.folder, "M1", TODAY)

    def test_a_member_owing_more_than_the_limit_is_refused(self) -> None:
        save_loans(self.folder, [late("B1", "M2", 41)])
        with self.assertRaises(Refused):
            check(self.folder, "M2", TODAY)
