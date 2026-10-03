"""The reservations: who waits for a book that is out, and for whom a returned book is held.

The queue of a book is the order of its lines in the file. The first of the queue gets the hold
when the book comes back, and keeps it through HOLD_DAYS days.
"""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from lending import loans, notices, store
from lending.catalog import load_books
from lending.loans import Loan, Refused
from lending.members import load_members
from lending.notices import Notice

RESERVATIONS = "reservations.jsonl"
HOLD_DAYS = 5


@dataclass(frozen=True)
class Reservation:
    book: str
    member: str
    reserved: date
    held: date | None = None  # the day the book started to be held for the member


def load_reservations(folder: Path) -> list[Reservation]:
    """Return the reservations in the order they were made."""
    return [
        Reservation(
            record["book"],
            record["member"],
            date.fromisoformat(record["reserved"]),
            date.fromisoformat(record["held"]) if record["held"] else None,
        )
        for record in store.read(folder, RESERVATIONS)
    ]


def save_reservations(folder: Path, reservations: list[Reservation]) -> None:
    records = [
        {
            "book": each.book,
            "member": each.member,
            "reserved": each.reserved.isoformat(),
            "held": each.held.isoformat() if each.held else None,
        }
        for each in reservations
    ]
    store.write(folder, RESERVATIONS, records)


def holder_of(reservations: list[Reservation], book: str) -> str | None:
    """Return the member a book is held for, or None when it is not held."""
    return next((each.member for each in reservations if each.book == book and each.held), None)


def reserve(folder: Path, book: str, member: str, today: date) -> None:
    """Put a member at the end of the queue of a book that is out."""
    if book not in load_books(folder):
        raise Refused(f"unknown book: {book}")
    if member not in load_members(folder):
        raise Refused(f"unknown member: {member}")
    reservations = load_reservations(folder)
    loan = loans.open_loan_of(loans.load_loans(folder), book)
    if loan is None and holder_of(reservations, book) is None:
        raise Refused(f"{book} is on the shelf, it can be borrowed")
    if loan is not None and loan.member == member:
        raise Refused(f"{member} has {book} on loan")
    if any(each.book == book and each.member == member for each in reservations):
        raise Refused(f"{member} has already reserved {book}")
    save_reservations(folder, [*reservations, Reservation(book, member, today)])


def cancel(folder: Path, book: str, member: str, today: date) -> None:
    """Take a member out of the queue of a book; a hold they had passes to the next."""
    reservations = load_reservations(folder)
    theirs = [each for each in reservations if each.book == book and each.member == member]
    if not theirs:
        raise Refused(f"{member} has not reserved {book}")
    rest = [each for each in reservations if each != theirs[0]]
    if theirs[0].held:
        rest = hold_for_next(folder, rest, book, today)
    save_reservations(folder, rest)


def hold_for_next(
    folder: Path, reservations: list[Reservation], book: str, today: date
) -> list[Reservation]:
    """Hold a book for the first member of its queue, if any, and queue their notice."""
    first = next((each for each in reservations if each.book == book), None)
    if first is None:
        return reservations
    last_day = today + timedelta(days=HOLD_DAYS)
    text = f"{book} is held for you until {last_day}."
    notices.queue(folder, Notice(first.member, "hold", text, today))
    return [replace(each, held=today) if each == first else each for each in reservations]


def give_back(folder: Path, book: str, today: date) -> Loan:
    """Return a book, and hold it for the first member of its queue."""
    loan = loans.give_back(folder, book, today)
    save_reservations(folder, hold_for_next(folder, load_reservations(folder), book, today))
    return loan


def borrow(folder: Path, book: str, member: str, today: date) -> Loan:
    """Lend a book unless it is held for another member; a hold picked up is over."""
    reservations = load_reservations(folder)
    holder = holder_of(reservations, book)
    if holder not in (None, member):
        raise Refused(f"{book} is held for {holder}")
    loan = loans.borrow(folder, book, member, today)
    if holder == member:
        picked = [each for each in reservations if each.book == book and each.held]
        save_reservations(folder, [each for each in reservations if each not in picked])
    return loan


def expire(folder: Path, today: date) -> None:
    """Drop the holds whose last day is past, and pass each book to the next of its queue."""
    reservations = load_reservations(folder)
    limit = timedelta(days=HOLD_DAYS)
    for stale in [each for each in reservations if each.held and each.held + limit < today]:
        rest = [each for each in reservations if each != stale]
        reservations = hold_for_next(folder, rest, stale.book, today)
    save_reservations(folder, reservations)
