"""The reminders: one notice to each member who keeps books past their due date.

The outbox is the memory of the reminders: a member is left alone for QUIET_DAYS after a
reminder notice already queued for them.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from lending.fines import fine
from lending.loans import Loan, load_loans, overdue
from lending.notices import Notice, load_notices, queue

KIND = "reminder"
QUIET_DAYS = 7


@dataclass(frozen=True)
class Reminder:
    member: str
    books: list[str]
    total: Decimal


def remind(folder: Path, today: date) -> list[Reminder]:
    """Queue a reminder to each member with overdue loans, and return the reminders sent."""
    quiet = recently_reminded(load_notices(folder), today)
    late: dict[str, list[Loan]] = {}
    for loan in overdue(load_loans(folder), today):
        late.setdefault(loan.member, []).append(loan)
    sent = []
    for member in sorted(late):
        if member in quiet:
            continue
        total = sum((fine(loan, today) for loan in late[member]), Decimal("0.00"))
        reminder = Reminder(member, [loan.book for loan in late[member]], total)
        queue(folder, Notice(member, KIND, text_of(reminder), today))
        sent.append(reminder)
    return sent


def recently_reminded(sent: list[Notice], today: date) -> set[str]:
    """Return the members whose last reminder is less than QUIET_DAYS old."""
    since = today - timedelta(days=QUIET_DAYS)
    return {notice.to for notice in sent if notice.kind == KIND and notice.on > since}


def text_of(reminder: Reminder) -> str:
    books = ", ".join(reminder.books)
    return f"Overdue: {books}. Fines owed so far: {reminder.total:.2f}."
