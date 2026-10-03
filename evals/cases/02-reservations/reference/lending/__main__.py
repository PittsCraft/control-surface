"""The command line: python3 -m lending [--data DIR] [--today YYYY-MM-DD] <command> ...

Exit codes: 0 done, 1 refused by a rule of the library, 2 wrong usage.
The only module that reads the clock: below it, the date of the day is passed in.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from lending import fines, loans, notices, reservations
from lending.loans import Refused
from lending.notices import Notice


def run_borrow(args: argparse.Namespace) -> None:
    loan = reservations.borrow(args.data, args.book, args.member, args.today)
    print(f"{loan.book} {loan.member} due {loan.due}")


def run_return(args: argparse.Namespace) -> None:
    loan = reservations.give_back(args.data, args.book, args.today)
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


def run_reserve(args: argparse.Namespace) -> None:
    reservations.reserve(args.data, args.book, args.member, args.today)
    print(f"{args.book} {args.member} reserved")


def run_cancel(args: argparse.Namespace) -> None:
    reservations.cancel(args.data, args.book, args.member, args.today)
    print(f"{args.book} {args.member} cancelled")


def run_expire(args: argparse.Namespace) -> None:
    reservations.expire(args.data, args.today)


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

    reserve = commands.add_parser("reserve", help="queue a member for a book that is out")
    reserve.add_argument("book")
    reserve.add_argument("member")
    reserve.set_defaults(run=run_reserve)

    cancel = commands.add_parser("cancel", help="take a member out of the queue of a book")
    cancel.add_argument("book")
    cancel.add_argument("member")
    cancel.set_defaults(run=run_cancel)

    expire = commands.add_parser("expire", help="drop the holds not picked up in time")
    expire.set_defaults(run=run_expire)
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
