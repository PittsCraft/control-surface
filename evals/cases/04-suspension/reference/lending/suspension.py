"""The suspension: a member who owes too much in fines can no longer borrow.

What a member owes is computed on the spot from their open loans: nothing is stored.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from lending.fines import fine
from lending.loans import Refused, load_loans, open_loans
from lending.members import load_members

LIMIT = Decimal("10.00")


def owed(folder: Path, member: str, today: date) -> Decimal:
    """Return the sum of the fines of the open loans of a member as of today."""
    if member not in load_members(folder):
        raise Refused(f"unknown member: {member}")
    theirs = open_loans(load_loans(folder), member)
    return sum((fine(loan, today) for loan in theirs), Decimal("0.00"))


def check(folder: Path, member: str, today: date) -> None:
    """Refuse a member who owes more than LIMIT. At exactly LIMIT they can still borrow."""
    amount = owed(folder, member, today)
    if amount > LIMIT:
        raise Refused(f"{member} is suspended: {amount:.2f} owed in fines, more than {LIMIT}")
