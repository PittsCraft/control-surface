import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lending import store
from lending.__main__ import main

BOOKS = [
    {"id": "B1", "title": "Emma", "author": "Austen", "price": "12.50"},
    {"id": "B2", "title": "Walden", "author": "Thoreau", "price": "9.00"},
]
MEMBERS = [
    {"id": "M1", "name": "Avery Lane", "category": "student"},
    {"id": "M2", "name": "Robin Hale", "category": "staff"},
]


class CommandLineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        store.write(self.folder, "books.jsonl", BOOKS)
        store.write(self.folder, "members.jsonl", MEMBERS)

    def run_cli(self, today: str, *command: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--data", str(self.folder), "--today", today, *command])
        return code, out.getvalue(), err.getvalue()

    def test_borrow_prints_the_due_date(self) -> None:
        self.assertEqual(
            self.run_cli("2026-03-01", "borrow", "B1", "M1"), (0, "B1 M1 due 2026-03-15\n", "")
        )

    def test_a_refused_borrow_exits_1_with_its_reason_on_standard_error(self) -> None:
        self.run_cli("2026-03-01", "borrow", "B1", "M1")
        code, out, err = self.run_cli("2026-03-02", "borrow", "B1", "M2")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("B1", err)

    def test_return_prints_the_fine_with_two_decimals(self) -> None:
        self.run_cli("2026-03-01", "borrow", "B1", "M1")
        self.assertEqual(
            self.run_cli("2026-03-20", "return", "B1"), (0, "B1 returned, fine 0.75\n", "")
        )

    def test_a_return_with_a_fine_queues_a_notice_to_the_member(self) -> None:
        self.run_cli("2026-03-01", "borrow", "B1", "M1")
        self.run_cli("2026-03-20", "return", "B1")
        (notice,) = store.read(self.folder, "outbox.jsonl")
        self.assertEqual((notice["to"], notice["kind"], notice["on"]), ("M1", "fine", "2026-03-20"))
        self.assertIn("0.75", notice["text"])

    def test_a_return_within_the_grace_queues_no_notice(self) -> None:
        self.run_cli("2026-03-01", "borrow", "B1", "M1")
        self.assertEqual(
            self.run_cli("2026-03-17", "return", "B1"), (0, "B1 returned, fine 0.00\n", "")
        )
        self.assertEqual(store.read(self.folder, "outbox.jsonl"), [])

    def test_loans_prints_the_open_loans_in_the_order_of_the_file(self) -> None:
        self.run_cli("2026-03-01", "borrow", "B2", "M2")
        self.run_cli("2026-03-02", "borrow", "B1", "M1")
        self.assertEqual(
            self.run_cli("2026-03-03", "loans"),
            (0, "B2 M2 2026-03-01 2026-03-15\nB1 M1 2026-03-02 2026-03-16\n", ""),
        )
        self.assertEqual(
            self.run_cli("2026-03-03", "loans", "--member", "M1"),
            (0, "B1 M1 2026-03-02 2026-03-16\n", ""),
        )

    def test_fine_prints_the_fine_of_the_open_loan(self) -> None:
        self.run_cli("2026-03-01", "borrow", "B1", "M1")
        self.assertEqual(self.run_cli("2026-03-20", "fine", "B1"), (0, "0.75\n", ""))
        self.assertEqual(self.run_cli("2026-03-20", "fine", "B2")[0], 1)

    def test_a_fine_is_capped_at_the_price_of_the_book(self) -> None:
        self.run_cli("2026-03-01", "borrow", "B2", "M1")
        self.assertEqual(self.run_cli("2026-06-01", "fine", "B2"), (0, "9.00\n", ""))
        self.assertEqual(
            self.run_cli("2026-06-01", "return", "B2"), (0, "B2 returned, fine 9.00\n", "")
        )

    def test_wrong_usage_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            main(["--data", str(self.folder), "lend"])
        self.assertEqual(stop.exception.code, 2)
