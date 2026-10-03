import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from lending.loans import Loan, save_loans
from lending.notices import Notice, load_notices, queue
from lending.reminders import Reminder, remind

JANUARY_5 = date(2026, 1, 5)
TODAY = date(2026, 3, 20)


class RemindTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        loans = [
            Loan("B1", "M1", JANUARY_5, date(2026, 3, 10)),
            Loan("B2", "M1", JANUARY_5, date(2026, 3, 17)),
            Loan("B3", "M2", JANUARY_5, TODAY),
            Loan("B4", "M3", JANUARY_5, date(2026, 3, 1), returned=date(2026, 3, 12)),
        ]
        save_loans(self.folder, loans)

    def test_one_reminder_per_member_with_overdue_loans(self) -> None:
        sent = remind(self.folder, TODAY)
        self.assertEqual(sent, [Reminder("M1", ["B1", "B2"], Decimal("3.25"))])
        (notice,) = load_notices(self.folder)
        self.assertEqual((notice.to, notice.kind, notice.on), ("M1", "reminder", TODAY))
        self.assertEqual(notice.text, "Overdue: B1, B2. Fines owed so far: 3.25.")

    def test_a_member_is_left_alone_for_seven_days(self) -> None:
        remind(self.folder, TODAY)
        day_six = remind(self.folder, date(2026, 3, 26))
        self.assertEqual([reminder.member for reminder in day_six], ["M2"])
        day_seven = remind(self.folder, date(2026, 3, 27))
        self.assertEqual([reminder.member for reminder in day_seven], ["M1"])

    def test_only_reminders_count(self) -> None:
        queue(self.folder, Notice("M1", "fine", "Fine of 1.00.", date(2026, 3, 19)))
        self.assertEqual(len(remind(self.folder, TODAY)), 1)
