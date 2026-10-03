"""The fine of a loan: the money a member owes for a late return.

Pure: no file, no clock. The loan, the date of the day and the price are passed in.
"""

from datetime import date
from decimal import Decimal

from lending.loans import Loan

DAILY_FINE = Decimal("0.25")
GRACE_DAYS = 2


def days_late(loan: Loan, today: date) -> int:
    """Count the days past the due date, up to the return or else to today, never negative."""
    end = loan.returned if loan.returned is not None else today
    return max((end - loan.due).days, 0)


def fine(loan: Loan, today: date, price: Decimal | None) -> Decimal:
    """Return what the loan costs its member as of today.

    DAILY_FINE per day late after the first GRACE_DAYS, never more than the price of the book.
    A book whose price is unknown (None) is not capped.
    """
    amount = DAILY_FINE * max(days_late(loan, today) - GRACE_DAYS, 0)
    return amount if price is None else min(amount, price)
