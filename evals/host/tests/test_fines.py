import unittest
from datetime import date
from decimal import Decimal

from lending.fines import days_late, fine
from lending.loans import Loan

DUE = date(2026, 3, 15)


def loan(returned: date | None = None) -> Loan:
    return Loan("B1", "M1", date(2026, 3, 1), DUE, returned)


class FineTest(unittest.TestCase):
    def test_a_loan_due_today_is_not_late(self) -> None:
        self.assertEqual(fine(loan(), DUE), Decimal("0.00"))

    def test_a_quarter_per_day_from_the_day_after_the_due_date(self) -> None:
        self.assertEqual(fine(loan(), date(2026, 3, 16)), Decimal("0.25"))
        self.assertEqual(fine(loan(), date(2026, 3, 25)), Decimal("2.50"))

    def test_a_returned_loan_counts_to_its_return_date(self) -> None:
        back = loan(returned=date(2026, 3, 18))
        self.assertEqual(days_late(back, date(2026, 6, 1)), 3)
        self.assertEqual(fine(back, date(2026, 6, 1)), Decimal("0.75"))

    def test_a_fine_is_never_negative(self) -> None:
        self.assertEqual(fine(loan(), date(2026, 3, 5)), Decimal("0.00"))
        self.assertEqual(fine(loan(returned=date(2026, 3, 5)), date(2026, 3, 30)), Decimal("0.00"))
