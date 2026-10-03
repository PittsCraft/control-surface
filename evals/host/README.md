# lending

A command line tool for a library that lends books: who holds which book, until when, and what a
late return costs.

    python3 -m lending [--data DIR] [--today YYYY-MM-DD] <command> ...

`--data` is the data directory (default `data`) and `--today` the date of the day (default: the
real date). Both come before the command.

## Commands

- `borrow <book> <member>` records the loan and prints `<book> <member> due <date>`.
- `return <book>` closes the open loan of the book and prints `<book> returned, fine <amount>`.
- `loans [--member <member>]` prints the open loans, one per line, in the order of the file:
  `<book> <member> <borrowed> <due>`.
- `fine <book>` prints the fine of the open loan of the book as of today.

Amounts are printed with two decimals. Exit codes: 0 done, 1 refused by a rule of the library
(the reason goes to standard error), 2 wrong usage.

## Rules

- A loan lasts 14 days.
- A book already on loan cannot be borrowed. An unknown book or member is refused.
- The fine of a loan is 0.25 per day late, counted from the day after the due date to today, or
  to the return date once the book is back. It is never negative. A loan due today is not late.
- A return that costs a fine queues a notice of kind `fine` to the member, whose text gives the
  amount.

## Data

The data directory holds JSON Lines files, one JSON object per line. A missing file reads as
empty.

- `books.jsonl`: `{"id": "B1", "title": "Emma", "author": "Austen", "price": "12.50"}`. The
  price is text, read as a decimal. An old book may have no `price`: nobody knows it.
- `members.jsonl`: `{"id": "M1", "name": "Avery Lane", "category": "student"}`. The category is
  `student` or `staff`.
- `loans.jsonl`: `{"book": "B1", "member": "M1", "borrowed": "2026-03-01", "due": "2026-03-15",
  "returned": null}`. `returned` is the return date, or null while the loan is open. Returned
  loans stay in the file.
- `outbox.jsonl`: the notices waiting for the mailer, `{"to": "M1", "kind": "fine", "text":
  "...", "on": "2026-03-18"}`. `to` is a member id and `on` the day the notice was queued.

`data/` holds a few sample books and members.

## Architecture

    lending/__main__.py   the command line: parses, calls the domain, prints
    lending/loans.py      Loan, borrow, give_back, the open loans, the overdue ones
    lending/fines.py      fine(loan, today), the money a late loan costs
    lending/notices.py    queue a notice in the outbox
    lending/catalog.py    Book, load_books
    lending/members.py    Member, load_members
    lending/store.py      read and write the JSON Lines files

- The command line talks to the domain modules, and the domain modules to `store.py`.
- Only `store.py` touches files.
- `fines.py` is pure: no file, no clock.
- Dates are passed in: nothing below `__main__.py` reads the clock.
- A rule that refuses raises `Refused`; the command line turns it into exit code 1.

## Gate

    python3 -m unittest discover -s tests -q

The tests of a module are in `tests/test_<module>.py`, those of the command line in
`tests/test_cli.py`.
