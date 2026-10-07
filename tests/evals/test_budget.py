"""What a campaign spends, and where it stops (evals/surface_evals/budget.py)."""

from pathlib import Path

import pytest
from support import stream

from surface_evals.budget import LEDGER, Ledger
from surface_evals.sessions import read_log


def _ledger(out: Path, *, usd: float | None = None, points: float | None = None) -> Ledger:
    return Ledger.load(out, max_usd=usd, max_points=points)


def test_a_resumed_session_reports_its_total_and_is_paid_once(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.note(read_log(stream(tmp_path / "a.jsonl", session="s-1", cost=0.25)))
    ledger.note(read_log(stream(tmp_path / "b.jsonl", session="s-1", cost=1.0)))
    ledger.note(read_log(stream(tmp_path / "c.jsonl", session="s-2", cost=0.5)))
    assert ledger.usd == pytest.approx(1.5)
    assert ledger.sessions == 3


def test_the_rise_of_the_weekly_gauge_is_summed_and_a_reset_starts_again(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.note(read_log(stream(tmp_path / "a.jsonl", session="a", gauges=(0.36, 0.37), week=1)))
    ledger.note(read_log(stream(tmp_path / "b.jsonl", session="b", gauges=(0.39,), week=1)))
    assert ledger.points == pytest.approx(3.0)
    # The week turned: the gauge fell, and the count goes on from where it now stands.
    ledger.note(read_log(stream(tmp_path / "c.jsonl", session="c", gauges=(0.02, 0.03), week=2)))
    assert ledger.points == pytest.approx(4.0)
    # A session of the week before, noted late, moves nothing: neither a rise nor a fall.
    ledger.note(read_log(stream(tmp_path / "d.jsonl", session="d", gauges=(0.39, 0.4), week=1)))
    ledger.note(read_log(stream(tmp_path / "e.jsonl", session="e", gauges=(0.04,), week=2)))
    assert ledger.points == pytest.approx(5.0)


def test_readings_that_runs_played_together_note_out_of_order_count_once(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    # Four runs at once: each session is noted when it ends, with the readings it met on its way,
    # so the point from 0.06 to 0.07 comes back in every stream that crossed it.
    ledger.note(read_log(stream(tmp_path / "a.jsonl", session="a", gauges=(0.06, 0.07), week=1)))
    ledger.note(read_log(stream(tmp_path / "b.jsonl", session="b", gauges=(0.06, 0.07), week=1)))
    ledger.note(read_log(stream(tmp_path / "c.jsonl", session="c", gauges=(0.06,), week=1)))
    ledger.note(read_log(stream(tmp_path / "d.jsonl", session="d", gauges=(0.07, 0.08), week=1)))
    assert ledger.points == pytest.approx(2.0)
    # A stream that does not date its week reads the same: a lower reading is an older one.
    undated = _ledger(tmp_path / "undated")
    undated.note(read_log(stream(tmp_path / "e.jsonl", session="e", gauges=(0.36, 0.37))))
    undated.note(read_log(stream(tmp_path / "f.jsonl", session="f", gauges=(0.36, 0.38))))
    assert undated.points == pytest.approx(2.0)


def test_a_session_killed_before_its_result_costs_nothing_known(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.note(read_log(stream(tmp_path / "killed.jsonl", cost=None)))
    assert ledger.usd == 0
    assert ledger.sessions == 1


def test_the_ledger_stops_at_either_ceiling_and_says_which(tmp_path: Path) -> None:
    free = _ledger(tmp_path / "free")
    free.note(read_log(stream(tmp_path / "a.jsonl", cost=50.0, gauges=(0.1, 0.9))))
    assert free.exhausted() is None
    dollars = _ledger(tmp_path / "usd", usd=1.0)
    assert dollars.exhausted() is None
    dollars.note(read_log(stream(tmp_path / "b.jsonl", cost=1.0)))
    assert "1 USD" in str(dollars.exhausted())
    week = _ledger(tmp_path / "week", points=5)
    week.note(read_log(stream(tmp_path / "c.jsonl", gauges=(0.36, 0.40))))
    assert week.exhausted() is None
    week.note(read_log(stream(tmp_path / "d.jsonl", session="d", gauges=(0.41,))))
    assert "5" in str(week.exhausted())


def test_the_ledger_of_a_campaign_is_kept_in_its_folder(tmp_path: Path) -> None:
    first = _ledger(tmp_path)
    first.note(read_log(stream(tmp_path / "a.jsonl", cost=2.0, gauges=(0.36, 0.38))))
    assert (tmp_path / LEDGER).is_file()
    again = _ledger(tmp_path, usd=3.0)
    assert again.usd == pytest.approx(2.0)
    assert again.points == pytest.approx(2.0)
    assert again.sessions == 1
    # A new launch does not charge the rise of the gauge between two launches.
    again.note(read_log(stream(tmp_path / "b.jsonl", session="b", cost=0.5, gauges=(0.5,))))
    assert again.points == pytest.approx(2.0)
    assert again.exhausted() is None
