"""A toy project for the end to end tests, with a plan folder in a chosen state.

`build(state, dest)` makes `dest/shelf`, a git repository holding a small module, its tests and a
gate command, with `dest/origin.git` as its bare remote. It installs the chain from this clone,
then drives a plan folder to the chosen state: it writes the files the chain would have written
and records each event through the installed state script, so the journal is a real one. A plan
drafted has its draft pull request too, kept by the stand-in `gh` of `gh_stand_in.py`. Run as a
script, it builds a project and prints its path, or runs one headless session in it:

    python3 tests/e2e/toy/toy.py build <state> <dest>
    python3 tests/e2e/toy/toy.py run <project> <log> <prompt> [--resume <session id>]

A session is launched the way ADR 0025 describes, by the end to end tests and by hand
alike: it bypasses permissions, so it runs only in the container of `tests/e2e/Dockerfile`.
"""

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import IO

import gh_stand_in

CLONE = Path(__file__).resolve().parents[3]
SLUG = "csv-export"
SECOND_SLUG = "count-books"  # the other plan of a branch that carries two
BRANCH = f"feat/{SLUG}"
PULL_TITLE = "Export the shelf as CSV"
GATE_COMMAND = "python3 -m unittest discover -s tests -q"
STATE_SCRIPT = Path(".claude/skills/surface-status/scripts/surface-status")
SESSION_TIMEOUT = 30 * 60  # seconds: a session still running then is killed
KILL_ROUNDS = 50  # how many times a kill looks for what a session left at work
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Toy Developer",
    "GIT_AUTHOR_EMAIL": "developer@example.com",
    "GIT_COMMITTER_NAME": "Toy Developer",
    "GIT_COMMITTER_EMAIL": "developer@example.com",
}


# Set by the image of `tests/e2e/Dockerfile`: a session bypasses permissions only where it is set.
CONTAINER = "SURFACE_E2E_CONTAINER"


class OutsideContainerError(RuntimeError):
    """A session was asked for outside the container, where bypassing permissions is not safe."""

    def __init__(self) -> None:
        super().__init__(
            "a session bypasses permissions, which is not safe on this machine: run it in the"
            " container of tests/e2e/Dockerfile, as tests/e2e/README.md says"
        )


def in_container() -> bool:
    return os.environ.get(CONTAINER) == "1"


class State(StrEnum):
    """The prepared states, each named after the scenario that starts from it."""

    SPECS = "specs"  # the main branch, the chain installed, no plan yet
    SPECS_CI = "specs-ci"  # the same, with a CI that runs on every push and pull request
    # Planning under way: the plan folder is in the working tree, nothing of it committed yet.
    PLAN_WRITTEN = "plan-written"  # the interview closed and the plan written, no blueprint
    BLUEPRINT_DRAWN = "blueprint-drawn"  # the blueprint drawn too, and not cross-checked
    PLANNING_CEILING = "planning-ceiling"  # two cross-checks with an omission, a ceiling of one
    AWAITING = "awaiting-approval"  # a plan drafted at revision 1, pushed, its draft opened
    UNPUSHED = "unpushed"  # that plan drafted and committed, never pushed: no draft opened
    UNPUSHED_CI = "unpushed-ci"  # the same, under the CI that runs on every push
    TWO_PLANS = "two-plans"  # a second plan drafted on the same branch
    SLICE_UNCOMMITTED = "slice-uncommitted"  # approved, slice 1 recorded and not committed
    SUSPECTED_BREAK = "suspected-break"  # slice 2 stopped on a break its executor suspects
    UNFOUNDED_SUSPICION = "unfounded-suspicion"  # the same, on a suspicion that is none
    BLUEPRINT_MODIFIED = "blueprint-modified"  # approved, slice 1 done, then the blueprint edited
    DEVELOPER_BREAK = "developer-break"  # every slice done, then a commit against the schema
    PROPOSED = "plan-change-proposed"  # that break raised by a review, committed, not pushed
    FIXING = "fixing"  # a defect and the review that found it: a fix is due
    CEILING = "ceiling"  # a defect, its review, a fix that missed it, a ceiling of one pass
    BLOCKED = "blocked"  # the ceiling reached: a second review finds the defect, then blocked
    # The states the evaluations review: every slice done, nothing reviewed yet.
    DONE = "done"  # the work as planned
    DEFECT = "defect"  # a defect the tests do not see: lines sorted by title only
    DEVIATION = "deviation"  # the tests of slice 1 in another file than the plan names
    SLOW_GATE = "slow-gate"  # the work as planned, and a gate that lasts
    REVIEW_UNRECORDED = "review-unrecorded"  # gates green, a clean review written, not recorded


def plan_name(slug: str = SLUG) -> str:
    return f"{datetime.now(UTC).date().isoformat()}-{slug}"


# The toy project, before the feature.

README = """\
# shelf

A shelf of books, kept as a JSON Lines file, one book per line with its `title`, `author`, `year`
and `isbn`.

    python3 -m shelf list books.jsonl

## Gates

    python3 -m unittest discover -s tests -q

## Conventions

- Branches: `feat/<slug>` for a feature.
- Commits: `<area>: <what changes>`, in the imperative, for example `books: read the isbn`.
- Standard library only.
"""

BOOKS = '''\
"""The books of the shelf, read from a JSON Lines file."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Book:
    title: str
    author: str
    year: int
    isbn: str


def load(path: Path) -> list[Book]:
    """Return the books of a shelf file, in the order of its lines."""
    books = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            books.append(
                Book(record["title"], record["author"], int(record["year"]), record["isbn"])
            )
    return books
'''

MAIN_BEFORE = '''\
"""The command line: python3 -m shelf <command> <shelf file>."""

import argparse
import sys
from pathlib import Path

from shelf.books import load


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shelf")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="print the books, one per line")
    listing.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    for book in load(args.path):
        print(f"{book.title} ({book.year}), {book.author}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

TEST_BOOKS = """\
import tempfile
import unittest
from pathlib import Path

from shelf.books import Book, load

LINE = '{"title": "Dune", "author": "Herbert", "year": 1965, "isbn": "9780441013593"}'


class LoadTest(unittest.TestCase):
    def test_reads_one_book_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "books.jsonl"
            path.write_text(LINE + "\\n\\n", encoding="utf-8")
            self.assertEqual(load(path), [Book("Dune", "Herbert", 1965, "9780441013593")])


if __name__ == "__main__":
    unittest.main()
"""

TEST_CLI_BEFORE = """\
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from shelf.__main__ import main

LINES = (
    '{"title": "Dune", "author": "Herbert", "year": 1965, "isbn": "9780441013593"}\\n'
    '{"title": "Emma", "author": "Austen", "year": 1815, "isbn": "9780141439587"}\\n'
)


def run(*argv: str) -> str:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "books.jsonl"
        path.write_text(LINES, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([*argv, str(path)])
        assert code == 0
        return out.getvalue()


class ListTest(unittest.TestCase):
    def test_prints_one_book_per_line(self) -> None:
        self.assertEqual(run("list"), "Dune (1965), Herbert\\nEmma (1815), Austen\\n")


if __name__ == "__main__":
    unittest.main()
"""

AGENTS_MD = """\
# shelf

Critical zone: the CSV export is read by the bookshop's spreadsheet import. Its columns, their
order and their names are a contract with the bookshop.
"""

# A CI that reacts to a push of any branch and to a pull request, a draft included: what
# /surface-plan warns about before the first push of a branch.
CI_PATH = ".github/workflows/ci.yml"
CI = """\
name: ci
on:
  push:
  pull_request:
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 -m unittest discover -s tests -q
"""

# A test that lasts, on the main branch: the gate then runs long enough for a session to be
# killed in it, and no review meets the file, which the branch does not change.
SLOW_SECONDS = 20
TEST_SLOW = f"""\
import time
import unittest


class SlowTest(unittest.TestCase):
    def test_the_shelf_takes_its_time(self) -> None:
        time.sleep({SLOW_SECONDS})


if __name__ == "__main__":
    unittest.main()
"""

# The plan folder, as /surface-plan leaves it at revision 1.

SPECS = """\
# Export the shelf as CSV

The bookshop wants to load our shelf into its spreadsheet. Add a command that prints the books
of a shelf file as CSV on standard output: one header line, then one line per book with its
title, author and year, sorted by author then title. The ISBN stays out of it for now.
"""

EXPLORATION = """\
# Exploration: export the shelf as CSV

## Repository rules

- Domain: a `Book` has a `title`, an `author`, a `year` and an `isbn` (`shelf/books.py`); a shelf
  file is JSON Lines, read by `load`.
- Architecture: `shelf/books.py` holds the domain and the reading, `shelf/__main__.py` the command
  line. Standard library only (README).
- Generated artifacts: none.
- Gates: `python3 -m unittest discover -s tests -q`, the only one (README). It is the gate of the
  plan.
- Conventions: branches `feat/<slug>`; commits `<area>: <what changes>`, imperative. No pull
  request convention stated.
- Decisions: not recorded anywhere.
- CI: none.

## What the feature touches

- Domain objects: `Book`, read only. Precedent: the `list` command of `shelf/__main__.py`.
- Settled by the code: a shelf file is read by `load`, and nothing is persisted. Left open: how
  fields are quoted, and what an empty shelf prints.

## Project declarations

`AGENTS.md`: the CSV export is a contract with the bookshop, its columns, their order and their
names.

## Read

README.md, AGENTS.md, shelf/books.py, shelf/__main__.py, tests/test_books.py, tests/test_cli.py.
"""

INTERVIEW = """\
# Interview: export the shelf as CSV

## Questions

### Q1. How are fields quoted?

Options:
- A. The default of Python's `csv` module: quoted only when they hold a comma, a quote or a line
  break.
- B. Every field quoted.

Recommended: A, spreadsheets read both and A keeps the file readable.

Answer (2026-09-29): A.

### Q2. What does an empty shelf print?

Options:
- A. The header line alone.
- B. Nothing.

Recommended: A, the import expects the header.

Answer (2026-09-29): A, the header alone.

## Amendments

## Plan change decisions

## Instructions after a block

## Git
"""

PLAN = """\
# Plan: export the shelf as CSV

Revision 1. Sources: `specs.md`, `exploration.md`, `interview.md`.

`python3 -m shelf export <file>` prints the books of a shelf file as CSV. The ISBN is not
exported.

## Acceptance criteria

1. `python3 -m shelf export <file>` prints the books of the file as CSV on standard output and
   exits with 0.
2. The first line is the header `title,author,year`.
3. One line per book: its title, author and year, in that order. The ISBN is not exported.
4. The lines are sorted by author, then by title.
5. Fields are quoted as Python's `csv` module does by default (Q1).
6. An empty shelf prints the header alone (Q2).

## Design

- The CSV is built by a pure function `to_csv(books: list[Book]) -> str` in a new module
  `shelf/export.py`, with the standard `csv` module, lines ended by `\\n`. The command line only
  reads the file and writes the text. Considered: writing in `__main__.py` directly, set aside
  because the function is easier to test alone.
- Standard library only, as the README requires.
- Assumption: the year is written as a whole number, as `Book` holds it.
- Assumption: lines end with `\\n`, the spreadsheet reads it.

## Slices

Each slice ends with the gate green, and its commit follows `<area>: <what changes>`.

<!-- slice:1 -->
### Slice 1: the CSV of a list of books

- Goal: `to_csv` in `shelf/export.py`: the header, then one row per book sorted by author then
  title.
- Files: `shelf/export.py`, `tests/test_export.py`.
- Precedent: none.
- Tests: unit tests of `to_csv`: the header, one book, the order by author then title with
  books whose title order differs, a title holding a comma, an empty list.
- Done when: the tests of criteria 2 to 6 pass.

<!-- slice:2 -->
### Slice 2: the export command

- Goal: the `export` subcommand of `shelf/__main__.py`, which writes `to_csv(load(path))`.
- Files: `shelf/__main__.py`, `tests/test_cli.py`.
- Precedent: the `list` subcommand.
- Tests: the command on a temporary shelf file, as the test of `list` does.
- Done when: a test runs `main(["export", path])` and reads the CSV (criterion 1).
- Depends on: slice 1.

## Gates

The gate the README names, the only one.

```gates
python3 -m unittest discover -s tests -q
```
"""

BLUEPRINT = """\
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

In scope: the `export` command and the CSV it prints. Out of scope: the ISBN, any other format,
writing to a file.

## The export command

`python3 -m shelf export <file>` loads the books of the file, sorts them by author, then by
title, and prints the CSV on standard output: the header, then one row per book.

The CSV is the only data the feature adds, the shelf file and its books are read and never
written. It has three columns, in this order:

| Column | From | Form |
|---|---|---|
| `title` | `Book.title` | text |
| `author` | `Book.author` | text |
| `year` | `Book.year` | whole number |

```mermaid
flowchart LR
  cli["shelf/__main__.py: export"] --> load["shelf/books.py: load (existing)"]
  cli --> csv["shelf/export.py: to_csv"]
```

`to_csv` is pure: a list of books in, the CSV text out. Standard library only.

Lines end with `\\n`, not with the `\\r\\n` Python's `csv` module writes by default: an assumption,
the spreadsheet reads it.

## Sensitive zones

Critical zone touched: the CSV export (`AGENTS.md`). Its columns are a contract with the
bookshop: their names and their order are fixed by this blueprint.

No change: state machines.
"""

CHECK = """\
omissions: 0

The blueprint shows what the plan does: the command, the three columns and their order, the
order of the lines, the quoting, the empty shelf, and the ISBN left out.
"""

DOCUMENTS = {
    "specs.md": SPECS,
    "exploration.md": EXPLORATION,
    "interview.md": INTERVIEW,
    "plan.md": PLAN,
    "blueprint.md": BLUEPRINT,
}

# Under the CI of `CI`, the exploration names it: a session reads there what triggers it.
EXPLORATION_CI = EXPLORATION.replace(
    "- CI: none.",
    f"- CI: `{CI_PATH}` runs the gate on every push, of any branch, and on every pull\n"
    "  request, a draft included.",
)

# The plan of the planning ceiling: the specs ask for an effect on the developer's file, the plan
# does it, and the blueprint, left as it is, says the file is never written.
SPECS_REWRITING = SPECS.replace(
    "The ISBN stays out of it for now.\n",
    "The ISBN stays out of it for now. Once the\n"
    "CSV is printed, the command rewrites the shelf file with its books in that same order.\n",
)

PLAN_REWRITING = (
    PLAN.replace(
        "6. An empty shelf prints the header alone (Q2).\n",
        "6. An empty shelf prints the header alone (Q2).\n"
        "7. Once the CSV is printed, the shelf file is rewritten with its books in that order.\n",
    )
    .replace(
        "- Standard library only, as the README requires.\n",
        "- Standard library only, as the README requires.\n"
        "- Once the CSV is printed, the command rewrites the shelf file with its books in the\n"
        "  sorted order, replacing the file the developer gave.\n",
    )
    .replace(
        "which writes `to_csv(load(path))`.\n",
        "which writes `to_csv(load(path))`,\n"
        "  then rewrites the shelf file in the sorted order (criterion 7).\n",
    )
)

# The two cross-checks that found it: the second is the pass after a ceiling of one.
CHECK_OMISSION = """\
omissions: 1

## Omission 1: the shelf file is rewritten

`plan.md`, acceptance criterion 7 and the last point of its design: once the CSV is printed, the
command rewrites the shelf file with its books in the sorted order, replacing the file the
developer gave. The blueprint shows no such effect, and says in "The export command" that the
shelf file and its books are read and never written: an irreversible operation on the developer's
data that the person who validates the blueprint has not seen. It belongs in "The export command",
with an acceptance criterion that states it.
"""

CHECK_OMISSION_AGAIN = CHECK_OMISSION.replace(
    "## Omission 1: the shelf file is rewritten",
    "## Omission 1: the shelf file is rewritten, still not shown",
)

# The other plan of a branch that carries two: a command that counts the books.
SECOND_DOCUMENTS = {
    "specs.md": """\
# Count the books of a shelf

Add a command that prints how many books a shelf file holds: a whole number, alone on its line.
""",
    # The rules of the repository are the same for both plans.
    "exploration.md": EXPLORATION.partition("## What the feature touches")[0].replace(
        "export the shelf as CSV", "count the books of a shelf"
    )
    + """\
## What the feature touches

- Domain objects: `Book`, read only. Precedent: the `list` command of `shelf/__main__.py`.
- Settled by the code: a shelf file is read by `load`, which skips its blank lines. Left open:
  nothing.

## Project declarations

`AGENTS.md`: the CSV export is a contract with the bookshop. The count does not touch it.

## Read

README.md, AGENTS.md, shelf/books.py, shelf/__main__.py, tests/test_cli.py.
""",
    "interview.md": """\
# Interview: count the books of a shelf

## Questions

The specs and the code leave nothing open.

## Amendments

## Plan change decisions

## Instructions after a block

## Git
""",
    "plan.md": """\
# Plan: count the books of a shelf

Revision 1. Sources: `specs.md`, `exploration.md`, `interview.md`.

`python3 -m shelf count <file>` prints how many books a shelf file holds.

## Acceptance criteria

1. `python3 -m shelf count <file>` prints the number of books of the file, alone on its line, and
   exits with 0.
2. An empty shelf prints `0`.

## Design

- The `count` subcommand of `shelf/__main__.py` prints `len(load(path))`. Standard library only.

## Slices

<!-- slice:1 -->
### Slice 1: the count command

- Goal: the `count` subcommand of `shelf/__main__.py`.
- Files: `shelf/__main__.py`, `tests/test_cli.py`.
- Precedent: the `list` subcommand.
- Tests: the command on a temporary shelf file, and on an empty one.
- Done when: the tests of criteria 1 and 2 pass.

## Gates

The gate the README names, the only one.

```gates
python3 -m unittest discover -s tests -q
```
""",
    "blueprint.md": """\
# Count the books of a shelf: blueprint

Revision 1, drawn from `plan.md`.

## The idea in one sentence

A new command prints how many books a shelf file holds.

## Acceptance criteria

1. `python3 -m shelf count <file>` prints the number of books of the file, alone on its line, and
   exits with 0.
2. An empty shelf prints `0`.

## Scope and out of scope

In scope: the `count` command. Out of scope: any filter, any other output.

## The count command

`python3 -m shelf count <file>` loads the books of the file and prints how many they are. The
shelf file is read and never written.

## Sensitive zones

Critical zones touched: none. The CSV export (`AGENTS.md`) is left as it is.

No change: data schema, sequences, state machines, algorithms.
""",
}

SECOND_CHECK = """\
omissions: 0

The blueprint shows what the plan does: the command, and what an empty shelf prints.
"""

# The feature, as the executors would have written it.

EXPORT = '''\
"""The shelf as CSV, for the bookshop's spreadsheet."""

import csv
import io

from shelf.books import Book

HEADER = ("title", "author", "year")


def to_csv(books: list[Book]) -> str:
    """Return the header, then one row per book, sorted by author then title."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerow(HEADER)
    for book in sorted(books, key=lambda book: (book.author, book.title)):
        writer.writerow((book.title, book.author, book.year))
    return out.getvalue()
'''

# The defect of the ceiling scenario: sorted by title alone, which the tests below do not see.
EXPORT_DEFECT = EXPORT.replace(
    "key=lambda book: (book.author, book.title)", "key=lambda book: book.title"
)

# The first review of the ceiling scenario, which found that defect.
REVIEW_OF_THE_DEFECT = """\
# Review 1

## Finding 1: the lines are sorted by title alone

Class: defect. Acceptance criterion 4 sorts the lines by author, then by title. `to_csv` in
`shelf/export.py` sorts them by `book.title` alone, and no test has two authors whose order by
title differs. Fix: sort by `(book.author, book.title)`, with a test that tells the two apart.

## Counts

defects 1, deviations 0, breaks 0
"""

# The second review of the ceiling, once the fix missed the defect: the pass after the ceiling.
REVIEW_OF_THE_MISSED_FIX = """\
# Review 2

## Finding 1: the lines are still sorted by title alone

Class: defect. The fix after review 1 left `to_csv` in `shelf/export.py` as it was: it still sorts
by `book.title` alone, against acceptance criterion 4, and still no test has two authors whose
order by title differs. Fix: sort by `(book.author, book.title)`, with a test that tells the two
apart.

## Counts

defects 1, deviations 0, breaks 0
"""

WHY_BLOCKED = "the lines are still sorted by title alone after a fix: criterion 4 is not met"

# The review of the break scenario, and the plan change it proposes to the developer.
REVIEW_OF_THE_BREAK = """\
# Review 1

## Finding 1: the export has a fourth column, `isbn`

Class: contract break. Acceptance criterion 2 of the blueprint fixes the header as
`title,author,year`, and criterion 3 says the ISBN is not exported. Since the commit "export: add
the isbn column, the bookshop asked for it", which belongs to no plan and so is the developer's,
`HEADER` in `shelf/export.py` holds `isbn` and `to_csv` writes `book.isbn` in every row. The CSV
export is the critical zone `AGENTS.md` declares: its columns are a contract with the bookshop.
The code does what that commit means, so the blueprint must change for it to stay true:
`plan-changes/01.md`.

## Counts

defects 0, deviations 0, breaks 1
"""

PROPOSAL = """\
# Plan change proposal 1: export the ISBN as a fourth column

## What would change in the blueprint

- Acceptance criterion 2: the header becomes `title,author,year,isbn`.
- Acceptance criterion 3: one line per book holds its title, author, year and ISBN, in that order.
- Scope: the ISBN moves in scope.
- The table of the columns gains a fourth row: `isbn`, from `Book.isbn`, text.

## Why

A commit of the developer, "export: add the isbn column, the bookshop asked for it", adds the
column to `shelf/export.py` and to its tests. The blueprint the developer approved says the ISBN
is not exported. Both cannot hold: either the blueprint takes the column, or the code drops it.

## Proof

`shelf/export.py`: `HEADER = ("title", "author", "year", "isbn")`, and each row ends with
`book.isbn`. `tests/test_export.py` and `tests/test_cli.py` expect the four columns, and the gates
are green: `gates/run-01.txt`.
"""

# A review that finds nothing, and the proof of conformity its reviewer leaves with it.
REVIEW_CLEAN = """\
# Review 1

No finding. The branch does what the plan says, the plan stays consistent with the blueprint, and
`blueprint.md` is the approved one. The gates are green: `gates/run-01.txt`.

## Counts

defects 0, deviations 0, breaks 0
"""

CONFORMITY = """\
# Conformity: export the shelf as CSV

Blueprint revision 1, approved and unchanged. Review: `reviews/pass-01.md`. Gates:
`gates/run-01.txt`, green.

1. `python3 -m shelf export <file>` prints the CSV and exits with 0: the `export` subcommand of
   `shelf/__main__.py`; `tests/test_cli.py`, `ExportTest.test_prints_the_csv`.
2. The header is `title,author,year`: `HEADER` in `shelf/export.py`; `tests/test_export.py`,
   `test_header_alone_for_an_empty_shelf`.
3. One line per book, its title, author and year, without the ISBN: `to_csv` in
   `shelf/export.py`; `test_one_row_per_book_without_the_isbn`.
4. Sorted by author, then by title: the key of `sorted` in `to_csv`;
   `test_sorted_by_author_then_title`, whose books come in the other order by title.
5. Quoted as the `csv` module does by default: `csv.writer` in `to_csv`; `test_a_comma_is_quoted`.
6. An empty shelf prints the header alone: `test_header_alone_for_an_empty_shelf`.

```critical-files
shelf/__main__.py
shelf/export.py
```
"""

TEST_EXPORT = """\
import unittest

from shelf.books import Book
from shelf.export import to_csv

EMMA = Book("Emma", "Austen", 1815, "9780141439587")
DUNE = Book("Dune", "Herbert", 1965, "9780441013593")


class ToCsvTest(unittest.TestCase):
    def test_header_alone_for_an_empty_shelf(self) -> None:
        self.assertEqual(to_csv([]), "title,author,year\\n")

    def test_one_row_per_book_without_the_isbn(self) -> None:
        self.assertEqual(to_csv([DUNE]), "title,author,year\\nDune,Herbert,1965\\n")

    def test_sorted_by_author_then_title(self) -> None:
        rows = to_csv([DUNE, EMMA]).splitlines()[1:]
        self.assertEqual(rows, ["Emma,Austen,1815", "Dune,Herbert,1965"])

    def test_a_comma_is_quoted(self) -> None:
        book = Book("Dune, Messiah", "Herbert", 1969, "9780593098233")
        self.assertEqual(to_csv([book]).splitlines()[1], '"Dune, Messiah",Herbert,1969')


if __name__ == "__main__":
    unittest.main()
"""

# With the defect, the order test keeps books whose title order is also their author order.
TEST_EXPORT_DEFECT = TEST_EXPORT.replace(
    'EMMA = Book("Emma", "Austen", 1815, "9780141439587")',
    'EMMA = Book("Clarissa", "Austen", 1815, "9780141439587")',
).replace('"Emma,Austen,1815"', '"Clarissa,Austen,1815"')

MAIN_AFTER = MAIN_BEFORE.replace(
    "from shelf.books import load\n",
    "from shelf.books import load\nfrom shelf.export import to_csv\n",
).replace(
    """    args = parser.parse_args(argv)
    for book in load(args.path):
""",
    """    exporting = commands.add_parser("export", help="print the books as CSV")
    exporting.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "export":
        sys.stdout.write(to_csv(load(args.path)))
        return 0
    for book in load(args.path):
""",
)

TEST_CLI_AFTER = TEST_CLI_BEFORE.replace(
    """

if __name__ == "__main__":""",
    """

class ExportTest(unittest.TestCase):
    def test_prints_the_csv(self) -> None:
        expected = "title,author,year\\nEmma,Austen,1815\\nDune,Herbert,1965\\n"
        self.assertEqual(run("export"), expected)


if __name__ == "__main__":""",
)

# With the defect, the test of the command keeps the same agreement of both orders.
TEST_CLI_DEFECT = TEST_CLI_AFTER.replace("Emma", "Clarissa")

# The developer's own commit of the break scenario: a fourth column, against the schema.
EXPORT_WITH_ISBN = EXPORT.replace(
    'HEADER = ("title", "author", "year")', 'HEADER = ("title", "author", "year", "isbn")'
).replace("(book.title, book.author, book.year)", "(book.title, book.author, book.year, book.isbn)")

TEST_EXPORT_WITH_ISBN = (
    TEST_EXPORT.replace("title,author,year", "title,author,year,isbn")
    .replace('"Emma,Austen,1815"', '"Emma,Austen,1815,9780141439587"')
    .replace('"Dune,Herbert,1965"', '"Dune,Herbert,1965,9780441013593"')
    .replace("Dune,Herbert,1965\\n", "Dune,Herbert,1965,9780441013593\\n")
    .replace("Herbert,1969'", "Herbert,1969,9780593098233'")
    .replace("without_the_isbn", "with_the_isbn")
)

TEST_CLI_WITH_ISBN = TEST_CLI_AFTER.replace(
    'expected = "title,author,year\\nEmma,Austen,1815\\nDune,Herbert,1965\\n"',
    'expected = (\n            "title,author,year,isbn\\n"\n'
    '            "Emma,Austen,1815,9780141439587\\n"\n'
    '            "Dune,Herbert,1965,9780441013593\\n"\n        )',
)

BLUEPRINT_EDITED = BLUEPRINT.replace(
    "3. One line per book: its title, author and year, in that order. The ISBN is not exported.",
    "3. One line per book: its title, author, year and ISBN, in that order.",
)

# The project of the suspected break: an `export` command exists before the feature, and prints
# the shelf as JSON for a backup. The plan and its blueprint, which call the command new, were
# drafted without seeing it: carrying out slice 2 would replace it, which the blueprint must say.
README_WITH_JSON_EXPORT = README.replace(
    "    python3 -m shelf list books.jsonl\n",
    "    python3 -m shelf list books.jsonl\n"
    "    python3 -m shelf export books.jsonl    # the shelf as JSON, read by the nightly backup\n",
)

MAIN_WITH_JSON_EXPORT = (
    MAIN_BEFORE.replace(
        "import argparse\nimport sys\n", "import argparse\nimport json\nimport sys\n"
    )
    .replace(
        "from pathlib import Path\n", "from dataclasses import asdict\nfrom pathlib import Path\n"
    )
    .replace(
        """    args = parser.parse_args(argv)
    for book in load(args.path):
""",
        """    exporting = commands.add_parser("export", help="the books as JSON, for the backup")
    exporting.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "export":
        json.dump([asdict(book) for book in load(args.path)], sys.stdout)
        sys.stdout.write("\\n")
        return 0
    for book in load(args.path):
""",
    )
)

TEST_CLI_WITH_JSON_EXPORT = TEST_CLI_BEFORE.replace(
    """

if __name__ == "__main__":""",
    """

class ExportTest(unittest.TestCase):
    def test_prints_the_shelf_as_json_for_the_backup(self) -> None:
        self.assertEqual([book["title"] for book in json.loads(run("export"))], ["Dune", "Emma"])


if __name__ == "__main__":""",
).replace("import io\n", "import io\nimport json\n")

# What the executor of slice 2 left when it stopped on that break: the test of the command it
# was about to write, and its reason in the journal.
TEST_CLI_OF_THE_SUSPECTED_BREAK = TEST_CLI_WITH_JSON_EXPORT.replace(
    """

if __name__ == "__main__":""",
    """

class ExportCsvTest(unittest.TestCase):
    def test_prints_the_csv(self) -> None:
        expected = "title,author,year\\nEmma,Austen,1815\\nDune,Herbert,1965\\n"
        self.assertEqual(run("export"), expected)


if __name__ == "__main__":""",
)

WHY_SUSPECTED = (
    "the export command exists already: it prints the shelf as JSON, which the README says the"
    " nightly backup reads; slice 2 would replace it, and the blueprint, which calls the command"
    " new, shows neither that the JSON export goes nor another name for the CSV one"
)

# A suspicion that is none: the executor of slice 2 wants a test helper the plan does not name,
# which changes nothing the blueprint shows.
TEST_SHELVES = '''\
"""Shelf files for the tests of the command line."""

import tempfile
from pathlib import Path

LINES = (
    '{"title": "Dune", "author": "Herbert", "year": 1965, "isbn": "9780441013593"}\\n'
    '{"title": "Emma", "author": "Austen", "year": 1815, "isbn": "9780141439587"}\\n'
)


def shelf_file() -> Path:
    """Write a shelf of two books in a temporary folder and return its path."""
    path = Path(tempfile.mkdtemp()) / "books.jsonl"
    path.write_text(LINES, encoding="utf-8")
    return path
'''

WHY_UNFOUNDED = (
    "slice 2 needs a helper module for its tests, tests/shelves.py, which builds the shelf files:"
    " neither the plan nor the diagram of the blueprint names that file"
)


# Building.


def git(project: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],  # noqa: S607 (git from the PATH, as the chain runs it)
        cwd=project,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def write(project: Path, files: Mapping[str, str]) -> None:
    for name, text in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def commit(project: Path, message: str, paths: Sequence[str]) -> None:
    git(project, "add", "--", *paths)
    git(project, "commit", "--quiet", "-m", message, "--", *paths)


def record(project: Path, plan: str, event: str, *options: str) -> dict[str, object]:
    """Record one event through the installed state script, which refuses an illegal one."""
    done = subprocess.run(
        [str(project / STATE_SCRIPT), "--json", "record", plan, event, *options],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        message = f"record {event} refused: {done.stdout}{done.stderr}"
        raise RuntimeError(message)
    answer: dict[str, object] = json.loads(done.stdout)
    return answer


def gate(project: Path, plan: str) -> str:
    """Run the gates of the approved plan through the installed state script; return the report."""
    done = subprocess.run(
        [str(project / STATE_SCRIPT), "--json", "gate", plan],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    answer: dict[str, object] = json.loads(done.stdout)
    if done.returncode != 0 or answer.get("result") != "pass":
        message = f"gate not green: {done.stdout}{done.stderr}"
        raise RuntimeError(message)
    return f"{plan}/{answer['report']}"


def show(project: Path, plan: str) -> dict[str, object]:
    done = subprocess.run(
        [str(project / STATE_SCRIPT), "--json", "show", plan],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    answer: dict[str, object] = json.loads(done.stdout)
    return answer


def pr_body(project: Path) -> str:
    """Give the pull request description the state script prints for the branch."""
    done = subprocess.run(
        [str(project / STATE_SCRIPT), "pr-body"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def critical_files(project: Path) -> list[str]:
    """List the files the pull request description gives the developer to read themselves."""
    done = subprocess.run(
        [str(project / STATE_SCRIPT), "--json", "pr-body"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        str(item["path"])
        for plan in json.loads(done.stdout)["plans"]
        for item in plan["critical_files"]
    ]


def check(project: Path) -> tuple[int, list[str]]:
    """Run the conformity check of the host's CI: its exit code, and the codes of what fails it."""
    done = subprocess.run(
        [str(project / STATE_SCRIPT), "--json", "check", "--require", "conformant"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    problems = [
        str(problem["code"])
        for plan in json.loads(done.stdout)["plans"]
        for problem in plan["problems"]
    ]
    return done.returncode, problems


def _base(dest: Path, settings: Mapping[str, object], more: Mapping[str, str]) -> Path:
    """Make the project on its main branch, pushed, with the chain installed and committed.

    `more` holds the files a state adds to the project before the feature: a CI, a slow test.
    """
    project = dest / "shelf"
    remote = dest / "origin.git"
    project.mkdir(parents=True)
    git(dest, "init", "--quiet", "--bare", "--initial-branch=main", str(remote))
    git(project, "init", "--quiet", "--initial-branch=main")
    for key, value in (
        ("user.name", "Toy Developer"),
        ("user.email", "developer@example.com"),
        ("commit.gpgsign", "false"),
        ("core.editor", "true"),
    ):
        git(project, "config", key, value)
    write(
        project,
        {
            "README.md": README,
            "AGENTS.md": AGENTS_MD,
            "shelf/__init__.py": "",
            "shelf/books.py": BOOKS,
            "shelf/__main__.py": MAIN_BEFORE,
            "tests/__init__.py": "",
            "tests/test_books.py": TEST_BOOKS,
            "tests/test_cli.py": TEST_CLI_BEFORE,
            ".gitignore": "__pycache__/\n",
            **more,
        },
    )
    git(project, "add", ".")
    git(project, "commit", "--quiet", "-m", "shelf: list the books of a shelf file")
    subprocess.run(
        [sys.executable, str(CLONE / "install.py"), str(project)],
        cwd=project,
        capture_output=True,
        check=True,
    )
    if settings:
        write(project, {".claude/surface.json": json.dumps(settings, indent=2) + "\n"})
    git(project, "add", ".claude")
    git(project, "commit", "--quiet", "-m", "chain: install the control surface")
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "--quiet", "--set-upstream", "origin", "main")
    git(project, "remote", "set-head", "origin", "main")
    return project


def _open(project: Path, slug: str, documents: Mapping[str, str]) -> str:
    """Open a plan folder with its documents and close its interview; nothing is committed."""
    plan = f"docs/plans/{plan_name(slug)}"
    write(project, {f"{plan}/{name}": text for name, text in documents.items()})
    record(project, plan, "plan-opened")
    record(project, plan, "interview-closed")
    return plan


def _check(project: Path, plan: str, number: int, report: str, omissions: int) -> None:
    name = f"checks/rev-01-{number:02d}.md"
    write(project, {f"{plan}/{name}": report})
    record(project, plan, "check-done", "--report", name, "--omissions", str(omissions))


def _draft(project: Path, plan: str, check: str, message: str) -> None:
    """Record a cross-check that found nothing, then the draft, and commit the plan folder."""
    _check(project, plan, 1, check, 0)
    record(project, plan, "plan-drafted")
    commit(project, message, [plan])


def _undrafted(project: Path, state: State) -> None:
    """Leave planning under way on the feature branch, as a session that died there would.

    Nothing of the plan folder is committed: /surface-plan commits at the draft and at the
    ceiling only.
    """
    git(project, "switch", "--quiet", "--create", BRANCH)
    if state is State.PLAN_WRITTEN:
        _open(
            project, SLUG, {name: DOCUMENTS[name] for name in DOCUMENTS if name != "blueprint.md"}
        )
    elif state is State.BLUEPRINT_DRAWN:
        _open(project, SLUG, DOCUMENTS)
    else:
        # The plan does what the specs ask and the blueprint does not show it. A ceiling of one
        # lets one rework run: the second check that finds it is the pass after the ceiling.
        documents = {**DOCUMENTS, "specs.md": SPECS_REWRITING, "plan.md": PLAN_REWRITING}
        plan = _open(project, SLUG, documents)
        _check(project, plan, 1, CHECK_OMISSION, 1)
        _check(project, plan, 2, CHECK_OMISSION_AGAIN, 1)


def _drafted(project: Path, state: State) -> str:
    """Draft a plan at revision 1 on its feature branch, push it and open its draft pull request.

    As /surface-plan would: the pull request is the one it opens at the first `plan-drafted`,
    kept by the stand-in `gh`, with the description of that moment. The later states leave it
    as it is, since the loop they prepare has not stopped yet, and a stop is what refreshes it.
    An unpushed state stops before the push, and so has no pull request.
    """
    git(project, "switch", "--quiet", "--create", BRANCH)
    under_ci = state is State.UNPUSHED_CI
    documents = {**DOCUMENTS, "exploration.md": EXPLORATION_CI} if under_ci else DOCUMENTS
    plan = _open(project, SLUG, documents)
    _draft(project, plan, CHECK, "plan: export the shelf as CSV, revision 1")
    if state is State.TWO_PLANS:
        second = _open(project, SECOND_SLUG, SECOND_DOCUMENTS)
        _draft(project, second, SECOND_CHECK, "plan: count the books of a shelf, revision 1")
    if state not in {State.UNPUSHED, State.UNPUSHED_CI}:
        git(project, "push", "--quiet", "--set-upstream", "origin", BRANCH)
        gh_stand_in.open_pull(
            project, head=BRANCH, base="main", title=PULL_TITLE, body=pr_body(project), draft=True
        )
    return plan


def _approve(project: Path, plan: str) -> None:
    record(project, plan, "plan-approved")
    commit(project, "plan: approve revision 1", [f"{plan}/journal.jsonl"])


def _slice(project: Path, plan: str, number: int, message: str, files: Mapping[str, str]) -> None:
    write(project, files)
    record(project, plan, "slice-done", "--slice", str(number), "--gates", GATE_COMMAND)
    commit(project, message, [*files, f"{plan}/journal.jsonl"])


def _slice_one_files(*, defect: bool, deviation: bool = False) -> dict[str, str]:
    # The deviation keeps the blueprint true, which says nothing of the tests: only the plan
    # names their file.
    tests = "tests/test_csv_rows.py" if deviation else "tests/test_export.py"
    return {
        "shelf/export.py": EXPORT_DEFECT if defect else EXPORT,
        tests: TEST_EXPORT_DEFECT if defect else TEST_EXPORT,
    }


def _slice_one(project: Path, plan: str, *, defect: bool, deviation: bool = False) -> None:
    files = _slice_one_files(defect=defect, deviation=deviation)
    _slice(project, plan, 1, "export: write a list of books as CSV", files)


def _slice_two(project: Path, plan: str, *, defect: bool) -> None:
    files = {
        "shelf/__main__.py": MAIN_AFTER,
        "tests/test_cli.py": TEST_CLI_DEFECT if defect else TEST_CLI_AFTER,
    }
    _slice(project, plan, 2, "export: add the export command", files)


def _developer_commit(project: Path, _plan: str) -> None:
    """Commit, as the developer, a fourth column the blueprint leaves out."""
    files = {
        "shelf/export.py": EXPORT_WITH_ISBN,
        "tests/test_export.py": TEST_EXPORT_WITH_ISBN,
        "tests/test_cli.py": TEST_CLI_WITH_ISBN,
    }
    write(project, files)
    commit(project, "export: add the isbn column, the bookshop asked for it", list(files))


def _review(  # noqa: PLR0913 (what a review leaves, each by its name)
    project: Path,
    plan: str,
    number: int,
    report: str,
    message: str,
    *,
    defects: int = 0,
    proposal: str | None = None,
) -> None:
    """Run the gates, record a review that left `report`, and commit both with the journal."""
    run = gate(project, plan)
    name = f"reviews/pass-{number:02d}.md"
    files = {f"{plan}/{name}": report}
    counts = ["--defects", str(defects), "--deviations", "0"]
    if proposal is None:
        counts += ["--breaks", "0"]
    else:
        files[f"{plan}/plan-changes/01.md"] = proposal
        counts += ["--breaks", "1", "--proposal", "plan-changes/01.md"]
    write(project, files)
    record(project, plan, "review-done", "--report", name, *counts)
    commit(project, message, [run, *files, f"{plan}/journal.jsonl"])


def _found_the_defect(project: Path, plan: str) -> None:
    """Record a review that finds the defect: a fix is due, and one pass is spent."""
    _review(project, plan, 1, REVIEW_OF_THE_DEFECT, "review: pass 1, one defect", defects=1)


def _reviewed_then_missed(project: Path, plan: str) -> None:
    """Record a review that finds the defect, then a fix that misses it: one pass is spent."""
    _found_the_defect(project, plan)
    run = gate(project, plan)
    record(project, plan, "fix-done")
    commit(project, "export: a fix that leaves the order as it was", [run, f"{plan}/journal.jsonl"])


def _blocked(project: Path, plan: str) -> None:
    """Go past the ceiling of one: a second review finds the defect again, and the loop blocks."""
    _reviewed_then_missed(project, plan)
    _review(project, plan, 2, REVIEW_OF_THE_MISSED_FIX, "review: pass 2, one defect", defects=1)
    record(project, plan, "blocked", "--why", WHY_BLOCKED)
    commit(project, "plan: blocked at the ceiling", [f"{plan}/journal.jsonl"])


def _break_raised(project: Path, plan: str) -> None:
    """Record the review that raises the developer's commit as a break, with its proposal.

    Committed and not pushed: the session that raised it died before the push of its stop.
    """
    _review(
        project, plan, 1, REVIEW_OF_THE_BREAK, "review: pass 1, a contract break", proposal=PROPOSAL
    )


def _review_left_unrecorded(project: Path, plan: str) -> None:
    """Leave what a reviewer wrote before its session died: a clean review, and its proof."""
    run = gate(project, plan)
    commit(project, "gates: run 1, green", [run, f"{plan}/journal.jsonl"])
    write(
        project, {f"{plan}/reviews/pass-01.md": REVIEW_CLEAN, f"{plan}/conformity.md": CONFORMITY}
    )


# What follows the slices in a state, before the push of the branch and after it.
_PUSHED: Mapping[State, Callable[[Path, str], None]] = {
    State.DEVELOPER_BREAK: _developer_commit,
    State.PROPOSED: _developer_commit,
    State.FIXING: _found_the_defect,
    State.CEILING: _reviewed_then_missed,
    State.BLOCKED: _blocked,
}
_NOT_PUSHED: Mapping[State, Callable[[Path, str], None]] = {
    State.PROPOSED: _break_raised,
    State.REVIEW_UNRECORDED: _review_left_unrecorded,
}
# What the executor of slice 2 left in the working tree, and the reason it recorded.
_SUSPICIONS: Mapping[State, tuple[Mapping[str, str], str]] = {
    State.SUSPECTED_BREAK: ({"tests/test_cli.py": TEST_CLI_OF_THE_SUSPECTED_BREAK}, WHY_SUSPECTED),
    State.UNFOUNDED_SUSPICION: ({"tests/shelves.py": TEST_SHELVES}, WHY_UNFOUNDED),
}
_ONE_PASS = frozenset({State.PLANNING_CEILING, State.CEILING, State.BLOCKED})
_WITH_THE_DEFECT = frozenset({State.FIXING, State.CEILING, State.BLOCKED, State.DEFECT})
_UNDRAFTED = frozenset({State.PLAN_WRITTEN, State.BLUEPRINT_DRAWN, State.PLANNING_CEILING})
_DRAFTED = frozenset({State.AWAITING, State.UNPUSHED, State.UNPUSHED_CI, State.TWO_PLANS})


def _executed(project: Path, plan: str, state: State) -> None:
    """Approve the plan and carry the loop to the state asked for."""
    _approve(project, plan)
    if state is State.SLICE_UNCOMMITTED:
        # The executor died between its record and its commit: the work and the journal line
        # are in the working tree.
        write(project, _slice_one_files(defect=False))
        record(project, plan, "slice-done", "--slice", "1", "--gates", GATE_COMMAND)
        return
    defect = state in _WITH_THE_DEFECT
    _slice_one(project, plan, defect=defect, deviation=state is State.DEVIATION)
    if state in _SUSPICIONS:
        # The executor recorded its reason and stopped: only a reviewer qualifies a break, and
        # the work of the slice waits for the verdict, uncommitted.
        left, why = _SUSPICIONS[state]
        write(project, left)
        record(project, plan, "break-suspected", "--slice", "2", "--why", why)
        return
    if state is State.BLUEPRINT_MODIFIED:
        write(project, {f"{plan}/blueprint.md": BLUEPRINT_EDITED})
        commit(project, "blueprint: export the isbn too", [f"{plan}/blueprint.md"])
    else:
        _slice_two(project, plan, defect=defect)
    if state in _PUSHED:
        _PUSHED[state](project, plan)
    git(project, "push", "--quiet", "origin", BRANCH)
    if state in _NOT_PUSHED:
        _NOT_PUSHED[state](project, plan)


def _more(state: State) -> dict[str, str]:
    """Give the files a state adds to the project before the feature."""
    if state in {State.SPECS_CI, State.UNPUSHED_CI}:
        return {CI_PATH: CI}
    if state is State.SLOW_GATE:
        return {"tests/test_slow.py": TEST_SLOW}
    if state is State.SUSPECTED_BREAK:
        return {
            "README.md": README_WITH_JSON_EXPORT,
            "shelf/__main__.py": MAIN_WITH_JSON_EXPORT,
            "tests/test_cli.py": TEST_CLI_WITH_JSON_EXPORT,
        }
    return {}


def build(state: State, dest: Path) -> Path:
    """Build the toy project under `dest` in `state` and return its path."""
    settings: dict[str, object] = {"max_autonomous_passes": 1} if state in _ONE_PASS else {}
    project = _base(dest, settings, _more(state))
    if state in {State.SPECS, State.SPECS_CI}:
        return project
    if state in _UNDRAFTED:
        _undrafted(project, state)
        return project
    plan = _drafted(project, state)
    if state not in _DRAFTED:
        _executed(project, plan, state)
    return project


# Running a headless session.


def claude_command(prompt: str, *, resume: str | None = None) -> list[str]:
    """Return the headless session of a scenario: a stream of JSON events, project settings only.

    User settings are left out, since their hooks, permissions and model would change the run, and
    so are MCP servers, which the chain does not use. Permissions are bypassed: nobody is there to
    answer, and what an agent runs to explore is not the chain's to list (ADR 0032). Refused
    outside the container, where a command could reach beyond the toy folder.
    """
    if not in_container():
        raise OutsideContainerError
    command = [
        "claude",
        "--print",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--setting-sources",
        "project,local",
        "--strict-mcp-config",
        "--permission-mode",
        "bypassPermissions",
    ]
    if resume is not None:
        command += ["--resume", resume]
    return command


def start_claude(
    project: Path, prompt: str, log: IO[str], *, resume: str | None = None
) -> subprocess.Popen[str]:
    """Start a session in its own process group, so that a scenario can kill all of it."""
    return subprocess.Popen(
        claude_command(prompt, resume=resume),
        cwd=project,
        stdin=subprocess.DEVNULL,  # an open standard input would be read as more prompt
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def at_work(project: Path) -> dict[int, str]:
    """Give the processes at work in a project, each with its command line.

    Read in `/proc`, so it finds them in the container only: a session, the commands it runs,
    and a gate, which the state script runs in a process group of its own (ADR 0034).
    """
    found: dict[int, str] = {}
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            where = (entry / "cwd").readlink()
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode().strip()
        except OSError:
            continue  # gone meanwhile
        if int(entry.name) != os.getpid() and where.is_relative_to(project):
            found[int(entry.name)] = command
    return found


def kill(session: subprocess.Popen[str], project: Path | None = None) -> None:
    """Kill a session and, when its project is given, what it left at work there.

    The group of the session does not hold a gate under way, nor a command a session started in
    a group of its own: they would go on writing in the project the next session takes up.
    """
    os.killpg(session.pid, signal.SIGKILL)
    session.wait()
    for _ in range(KILL_ROUNDS):
        left = {} if project is None else at_work(project)
        if not left:
            break
        for pid in left:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        time.sleep(0.1)


def run_session(project: Path, prompt: str, log: Path, *, resume: str | None = None) -> int | None:
    """Run one session to its end and return its exit code, or None once killed at the timeout."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as out:
        session = start_claude(project, prompt, out, resume=resume)
        try:
            return session.wait(timeout=SESSION_TIMEOUT)
        except subprocess.TimeoutExpired:
            kill(session)
            return None


def session_result(log: Path) -> dict[str, object]:
    """Return the last result of a session's stream: its id, its final message, its cost."""
    result: dict[str, object] = {}
    for raw in log.read_text(encoding="utf-8").splitlines():
        if raw.startswith("{"):
            line = json.loads(raw)
            if line.get("type") == "result":
                result = line
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The toy project of the end to end tests.")
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build", help="build the toy project in a chosen state")
    builder.add_argument("state", type=State, choices=list(State))
    builder.add_argument("dest", type=Path, help="an empty or missing folder")
    runner = commands.add_parser("run", help="run one headless session to its end")
    runner.add_argument("project", type=Path)
    runner.add_argument("log", type=Path, help="where the stream of the session goes")
    runner.add_argument("prompt", help="what the developer types, like /surface-execute")
    runner.add_argument("--resume", help="the id of the session to continue")
    args = parser.parse_args(argv)
    if args.command == "run" and not in_container():
        parser.error(str(OutsideContainerError()))
    if args.command == "build":
        dest: Path = args.dest.resolve()
        if dest.exists() and any(dest.iterdir()):
            parser.error(f"{dest} is not empty")
        sys.stdout.write(f"{build(args.state, dest)}\n")
        return 0
    code = run_session(args.project.resolve(), args.prompt, args.log, resume=args.resume)
    result = session_result(args.log)
    ended = "killed at the timeout" if code is None else f"exit code {code}"
    sys.stdout.write(
        f"{ended}, session {result.get('session_id')}, cost {result.get('total_cost_usd')} USD\n"
        f"{result.get('result', '')}\n"
    )
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
