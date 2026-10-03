import unittest
from datetime import date
from decimal import Decimal

from lending.fines import days_late, fine
from lending.loans import Loan

DUE = date(2026, 3, 15)
PRICE = Decimal("12.50")


def loan(returned: date | None = None) -> Loan:
    return Loan("B1", "M1", date(2026, 3, 1), DUE, returned)


class FineTest(unittest.TestCase):
    def test_a_loan_due_today_is_not_late(self) -> None:
        self.assertEqual(fine(loan(), DUE, PRICE), Decimal("0.00"))

    def test_the_first_two_days_late_are_free(self) -> None:
        self.assertEqual(fine(loan(), date(2026, 3, 16), PRICE), Decimal("0.00"))
        self.assertEqual(fine(loan(), date(2026, 3, 17), PRICE), Decimal("0.00"))

    def test_a_quarter_per_day_after_the_grace(self) -> None:
        self.assertEqual(fine(loan(), date(2026, 3, 18), PRICE), Decimal("0.25"))
        self.assertEqual(fine(loan(), date(2026, 3, 25), PRICE), Decimal("2.00"))

    def test_a_fine_never_exceeds_the_price(self) -> None:
        self.assertEqual(fine(loan(), date(2026, 3, 31), Decimal("3.50")), Decimal("3.50"))
        self.assertEqual(fine(loan(), date(2026, 9, 1), Decimal("3.50")), Decimal("3.50"))

    def test_an_unknown_price_does_not_cap(self) -> None:
        self.assertEqual(fine(loan(), date(2026, 6, 23), None), Decimal("24.50"))

    def test_a_returned_loan_counts_to_its_return_date(self) -> None:
        back = loan(returned=date(2026, 3, 20))
        self.assertEqual(days_late(back, date(2026, 6, 1)), 5)
        self.assertEqual(fine(back, date(2026, 6, 1), PRICE), Decimal("0.75"))

    def test_a_fine_is_never_negative(self) -> None:
        self.assertEqual(fine(loan(), date(2026, 3, 5), PRICE), Decimal("0.00"))
        early = loan(returned=date(2026, 3, 5))
        self.assertEqual(fine(early, date(2026, 3, 30), PRICE), Decimal("0.00"))
