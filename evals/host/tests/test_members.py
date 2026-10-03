import tempfile
import unittest
from pathlib import Path

from lending import store
from lending.members import Member, load_members


class LoadMembersTest(unittest.TestCase):
    def test_reads_the_members_by_id(self) -> None:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        records = [
            {"id": "M1", "name": "Avery Lane", "category": "student"},
            {"id": "M3", "name": "Morgan Reed", "category": "staff"},
        ]
        store.write(folder, "members.jsonl", records)
        self.assertEqual(
            load_members(folder),
            {
                "M1": Member("M1", "Avery Lane", "student"),
                "M3": Member("M3", "Morgan Reed", "staff"),
            },
        )
