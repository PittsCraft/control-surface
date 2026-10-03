import tempfile
import unittest
from pathlib import Path

from lending import store


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_a_missing_file_reads_as_empty(self) -> None:
        self.assertEqual(store.read(self.folder, "loans.jsonl"), [])

    def test_reads_one_record_per_line_and_skips_blank_lines(self) -> None:
        (self.folder / "books.jsonl").write_text('{"id": "B1"}\n\n{"id": "B2"}\n', encoding="utf-8")
        self.assertEqual(store.read(self.folder, "books.jsonl"), [{"id": "B1"}, {"id": "B2"}])

    def test_write_replaces_the_file(self) -> None:
        store.write(self.folder, "books.jsonl", [{"id": "B1"}])
        store.write(self.folder, "books.jsonl", [{"id": "B2"}])
        self.assertEqual(
            (self.folder / "books.jsonl").read_text(encoding="utf-8"), '{"id": "B2"}\n'
        )

    def test_append_adds_one_record_at_the_end(self) -> None:
        store.append(self.folder, "outbox.jsonl", {"to": "M1"})
        store.append(self.folder, "outbox.jsonl", {"to": "M2"})
        self.assertEqual(store.read(self.folder, "outbox.jsonl"), [{"to": "M1"}, {"to": "M2"}])
