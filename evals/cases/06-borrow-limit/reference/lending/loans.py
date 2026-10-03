"""The loans: who holds which book, since when and until when."""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from lending import store
from lending.catalog import load_books
from lending.members import load_members

LOANS = "loans.jsonl"
LOAN_DAYS = 14
MAX_OPEN_LOANS = {"student": 3, "staff": 6}


class Refused(Exception):
    """A rule of the library refuses what was asked."""


@dataclass(frozen=True)
class Loan:
    book: str
    member: str
    borrowed: date
    due: date
    returned: date | None = None


def load_loans(folder: Path) -> list[Loan]:
    """Return every loan, open or returned, in the order of the file."""
    return [
        Loan(
            record["book"],
            record["member"],
            date.fromisoformat(record["borrowed"]),
            date.fromisoformat(record["due"]),
            date.fromisoformat(record["returned"]) if record.get("returned") else None,
        )
        for record in store.read(folder, LOANS)
    ]


def save_loans(folder: Path, loans: list[Loan]) -> None:
    """Write every loan back, one line each, with the five fields of a loan line."""
    records = [
        {
            "book": loan.book,
            "member": loan.member,
            "borrowed": loan.borrowed.isoformat(),
            "due": loan.due.isoformat(),
            "returned": loan.returned.isoformat() if loan.returned else None,
        }
        for loan in loans
    ]
    store.write(folder, LOANS, records)


def open_loans(loans: list[Loan], member: str | None = None) -> list[Loan]:
    """Return the loans not returned yet, those of one member when it is given."""
    return [loan for loan in loans if loan.returned is None and member in (None, loan.member)]


def open_loan_of(loans: list[Loan], book: str) -> Loan | None:
    """Return the open loan of a book, or None when the book is on the shelf."""
    return next((loan for loan in open_loans(loans) if loan.book == book), None)


def overdue(loans: list[Loan], today: date) -> list[Loan]:
    """Return the open loans past their due date. A loan due today is not late."""
    return [loan for loan in open_loans(loans) if loan.due < today]


def borrow(folder: Path, book: str, member: str, today: date) -> Loan:
    """Record the loan of a book to a member, due LOAN_DAYS days from today.

    A member holds at most MAX_OPEN_LOANS open loans for their category.
    """
    if book not in load_books(folder):
        raise Refused(f"unknown book: {book}")
    members = load_members(folder)
    if member not in members:
        raise Refused(f"unknown member: {member}")
    loans = load_loans(folder)
    if open_loan_of(loans, book) is not None:
        raise Refused(f"{book} is already on loan")
    if len(open_loans(loans, member)) >= MAX_OPEN_LOANS[members[member].category]:
        raise Refused(f"{member} already holds too many books")
    loan = Loan(book, member, today, today + timedelta(days=LOAN_DAYS))
    save_loans(folder, [*loans, loan])
    return loan


def give_back(folder: Path, book: str, today: date) -> Loan:
    """Mark the open loan of a book as returned today, and return it."""
    loans = load_loans(folder)
    loan = open_loan_of(loans, book)
    if loan is None:
        raise Refused(f"{book} is not on loan")
    returned = replace(loan, returned=today)
    save_loans(folder, [returned if each is loan else each for each in loans])
    return returned
