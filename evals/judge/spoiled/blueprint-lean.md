# Export the shelf as CSV: blueprint

Revision 1, drawn from `plan.md`.

## The idea in one sentence

A new command prints the books of a shelf file as CSV, for the bookshop's spreadsheet.

## Acceptance criteria

1. `python3 -m shelf export <file>` prints the books of the file as CSV on standard output and
   exits with 0.
2. The first line is the header `title,author,year`.
3. One line per book: its title, author and year, in that order. The ISBN is not exported.
4. The lines are sorted by author, then by title.
5. Fields are quoted as Python's `csv` module does by default: only when they hold a comma, a
   quote or a line break.
6. An empty shelf prints the header alone.

## Scope and out of scope

Out of scope: any other format, writing to a file.

## The export command

The year is printed as the whole number the shelf file holds. Lines end with a line feed, not
with the carriage return and line feed Python's `csv` module writes by default: an assumption,
to confirm with the bookshop.

## Sensitive zones

Critical zone touched: the CSV export (`AGENTS.md`). Its columns are a contract with the
bookshop, fixed by criteria 2 and 3.

No change: the data schema, the architecture and its boundaries, the state machines.
