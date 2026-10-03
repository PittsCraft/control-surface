"""The command line: python3 -m lending [--data DIR] [--today YYYY-MM-DD] <command> ...

Exit codes: 0 done, 1 refused by a rule of the library, 2 wrong usage.
The only module that reads the clock: below it, the date of the day is passed in.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from lending import fines, loans, notices
from lending.loans import Refused
from lending.notices import Notice


def run_borrow(args: argparse.Namespace) -> None:
    loan = loans.borrow(args.data, args.book, args.member, args.today)
    print(f"{loan.book} {loan.member} due {loan.due}")


def run_return(args: argparse.Namespace) -> None:
    loan = loans.give_back(args.data, args.book, args.today)
    amount = fines.fine(loan, args.today)
    if amount:
        text = f"Fine of {amount:.2f} for the late return of {loan.book}."
        notices.queue(args.data, Notice(loan.member, "fine", text, args.today))
    print(f"{loan.book} returned, fine {amount:.2f}")


def run_loans(args: argparse.Namespace) -> None:
    for loan in loans.open_loans(loans.load_loans(args.data), args.member):
        print(f"{loan.book} {loan.member} {loan.borrowed} {loan.due}")


def run_fine(args: argparse.Namespace) -> None:
    loan = loans.open_loan_of(loans.load_loans(args.data), args.book)
    if loan is None:
        raise Refused(f"{args.book} is not on loan")
    print(f"{fines.fine(loan, args.today):.2f}")


def run_overdue(args: argparse.Namespace) -> None:
    late = loans.overdue(loans.load_loans(args.data), args.today)
    for loan in sorted(late, key=lambda loan: (loan.due, loan.book)):
        print(f"{loan.book} {loan.member} {loan.due} {fines.days_late(loan, args.today)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lending", description="A library that lends books.")
    parser.add_argument("--data", type=Path, default=Path("data"), help="the data directory")
    parser.add_argument("--today", type=date.fromisoformat, help="the date of the day")
    commands = parser.add_subparsers(dest="command", required=True)

    borrow = commands.add_parser("borrow", help="lend a book to a member")
    borrow.add_argument("book")
    borrow.add_argument("member")
    borrow.set_defaults(run=run_borrow)

    give_back = commands.add_parser("return", help="take a book back and print its fine")
    give_back.add_argument("book")
    give_back.set_defaults(run=run_return)

    listing = commands.add_parser("loans", help="print the open loans, one per line")
    listing.add_argument("--member", help="only the loans of this member")
    listing.set_defaults(run=run_loans)

    fine = commands.add_parser("fine", help="print the fine of the open loan of a book")
    fine.add_argument("book")
    fine.set_defaults(run=run_fine)

    overdue = commands.add_parser("overdue", help="print the late loans, the latest first")
    overdue.set_defaults(run=run_overdue)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.today is None:
        args.today = date.today()
    try:
        args.run(args)
    except Refused as refusal:
        print(refusal, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
