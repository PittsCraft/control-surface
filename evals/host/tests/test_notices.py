import tempfile
import unittest
from datetime import date
from pathlib import Path

from lending import store
from lending.notices import Notice, queue


class QueueTest(unittest.TestCase):
    def test_a_notice_is_added_at_the_end_of_the_outbox(self) -> None:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        queue(folder, Notice("M1", "fine", "first", date(2026, 3, 1)))
        queue(folder, Notice("M2", "fine", "second", date(2026, 3, 2)))
        self.assertEqual(
            store.read(folder, "outbox.jsonl"),
            [
                {"to": "M1", "kind": "fine", "text": "first", "on": "2026-03-01"},
                {"to": "M2", "kind": "fine", "text": "second", "on": "2026-03-02"},
            ],
        )
