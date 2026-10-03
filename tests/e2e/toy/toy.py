"""A toy project for the end to end tests, with a plan folder in a chosen state.

`build(state, dest)` makes `dest/shelf`, a git repository holding a small module, its tests and a
gate command, with `dest/origin.git` as its bare remote. It installs the chain from this clone,
then drives a plan folder to the chosen state: it writes the files the chain would have written
and records each event through the installed state script, so the journal is a real one. Run as a
script, it builds a project and prints its path, or runs one headless session in it:

    python3 tests/e2e/toy/toy.py build <state> <dest>
    python3 tests/e2e/toy/toy.py run <project> <log> <prompt> [--resume <session id>]

A session is launched the way ADR 0025 describes, by the end to end tests and by hand
alike: it bypasses permissions, so it runs only in the container of `tests/e2e/Dockerfile`.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import IO

CLONE = Path(__file__).resolve().parents[3]
SLUG = "csv-export"
BRANCH = f"feat/{SLUG}"
GATE_COMMAND = "python3 -m unittest discover -s tests -q"
STATE_SCRIPT = Path(".claude/skills/surface-status/scripts/surface-status")
SESSION_TIMEOUT = 30 * 60  # seconds: a session still running then is killed
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
    AWAITING = "awaiting-approval"  # a plan drafted at revision 1, pushed
    BLUEPRINT_MODIFIED = "blueprint-modified"  # approved, slice 1 done, then the blueprint edited
    DEVELOPER_BREAK = "developer-break"  # every slice done, then a commit against the schema
    CEILING = "ceiling"  # a defect, its review, a fix that missed it, a ceiling of one pass
    # The states the evaluations review: every slice done, nothing reviewed yet.
    DONE = "done"  # the work as planned
    DEFECT = "defect"  # a defect the tests do not see: lines sorted by title only
    DEVIATION = "deviation"  # the tests of slice 1 in another file than the plan names


def plan_name() -> str:
    return f"{datetime.now(UTC).date().isoformat()}-{SLUG}"


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

The CSV has three columns, in this order:

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


def _base(dest: Path, settings: Mapping[str, object]) -> Path:
    """Make the project on its main branch, pushed, with the chain installed and committed."""
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


def _awaiting(project: Path) -> str:
    """Draft a plan at revision 1 on its feature branch and push it, as /surface-plan would."""
    plan = f"docs/plans/{plan_name()}"
    git(project, "switch", "--quiet", "--create", BRANCH)
    write(
        project,
        {
            f"{plan}/specs.md": SPECS,
            f"{plan}/exploration.md": EXPLORATION,
            f"{plan}/interview.md": INTERVIEW,
            f"{plan}/plan.md": PLAN,
            f"{plan}/blueprint.md": BLUEPRINT,
            f"{plan}/checks/rev-01-01.md": CHECK,
        },
    )
    record(project, plan, "plan-opened")
    record(project, plan, "interview-closed")
    record(project, plan, "check-done", "--report", "checks/rev-01-01.md", "--omissions", "0")
    record(project, plan, "plan-drafted")
    commit(project, "plan: export the shelf as CSV, revision 1", [plan])
    git(project, "push", "--quiet", "--set-upstream", "origin", BRANCH)
    return plan


def _approve(project: Path, plan: str) -> None:
    record(project, plan, "plan-approved")
    commit(project, "plan: approve revision 1", [f"{plan}/journal.jsonl"])


def _slice(project: Path, plan: str, number: int, message: str, files: Mapping[str, str]) -> None:
    write(project, files)
    record(project, plan, "slice-done", "--slice", str(number), "--gates", GATE_COMMAND)
    commit(project, message, [*files, f"{plan}/journal.jsonl"])


def _slice_one(project: Path, plan: str, *, defect: bool, deviation: bool = False) -> None:
    # The deviation keeps the blueprint true, which says nothing of the tests: only the plan
    # names their file.
    tests = "tests/test_csv_rows.py" if deviation else "tests/test_export.py"
    files = {
        "shelf/export.py": EXPORT_DEFECT if defect else EXPORT,
        tests: TEST_EXPORT_DEFECT if defect else TEST_EXPORT,
    }
    _slice(project, plan, 1, "export: write a list of books as CSV", files)


def _slice_two(project: Path, plan: str, *, defect: bool) -> None:
    files = {
        "shelf/__main__.py": MAIN_AFTER,
        "tests/test_cli.py": TEST_CLI_DEFECT if defect else TEST_CLI_AFTER,
    }
    _slice(project, plan, 2, "export: add the export command", files)


def _reviewed_then_missed(project: Path, plan: str) -> None:
    """Record a review that finds the defect, then a fix that misses it: one pass is spent."""
    report = f"{plan}/reviews/pass-01.md"
    run = gate(project, plan)
    write(project, {report: REVIEW_OF_THE_DEFECT})
    review = ("--report", "reviews/pass-01.md", "--defects", "1", "--deviations", "0")
    record(project, plan, "review-done", *review, "--breaks", "0")
    commit(project, "review: pass 1, one defect", [run, report, f"{plan}/journal.jsonl"])
    run = gate(project, plan)
    record(project, plan, "fix-done")
    commit(project, "export: a fix that leaves the order as it was", [run, f"{plan}/journal.jsonl"])


def build(state: State, dest: Path) -> Path:
    """Build the toy project under `dest` in `state` and return its path."""
    settings: dict[str, object] = {}
    if state is State.CEILING:
        settings["max_autonomous_passes"] = 1
    project = _base(dest, settings)
    if state is State.SPECS:
        return project
    plan = _awaiting(project)
    if state is State.AWAITING:
        return project
    _approve(project, plan)
    defect = state in {State.CEILING, State.DEFECT}
    _slice_one(project, plan, defect=defect, deviation=state is State.DEVIATION)
    if state is State.BLUEPRINT_MODIFIED:
        write(project, {f"{plan}/blueprint.md": BLUEPRINT_EDITED})
        commit(project, "blueprint: export the isbn too", [f"{plan}/blueprint.md"])
    else:
        _slice_two(project, plan, defect=defect)
    if state is State.DEVELOPER_BREAK:
        files = {
            "shelf/export.py": EXPORT_WITH_ISBN,
            "tests/test_export.py": TEST_EXPORT_WITH_ISBN,
            "tests/test_cli.py": TEST_CLI_WITH_ISBN,
        }
        write(project, files)
        commit(project, "export: add the isbn column, the bookshop asked for it", list(files))
    if state is State.CEILING:
        _reviewed_then_missed(project, plan)
    git(project, "push", "--quiet", "origin", BRANCH)
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


def kill(session: subprocess.Popen[str]) -> None:
    os.killpg(session.pid, signal.SIGKILL)
    session.wait()


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
