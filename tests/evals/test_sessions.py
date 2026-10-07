"""What the stream of a session says (evals/surface_evals/sessions.py)."""

from pathlib import Path

import pytest
import toy
from support import stream

from surface_evals.sessions import Gauge, Launch, ask, named_in_tool_calls, read_log, run_chain


def test_a_stream_gives_its_session_its_cost_its_gauge_and_the_agents_launched(
    tmp_path: Path,
) -> None:
    path = stream(
        tmp_path / "plan.jsonl",
        session="s-9",
        cost=0.84,
        final="  Revision 1 is drafted.  ",
        gauges=(0.36, 0.37),
        week=1791864000,
        agents=(("Plan", "opus"), ("surface-extractor", None)),
    )
    log = read_log(path)
    assert log.session_id == "s-9"
    assert log.ended
    assert log.final == "Revision 1 is drafted."
    assert log.cost == pytest.approx(0.84)
    assert log.gauges == (Gauge(0.36, 1791864000), Gauge(0.37, 1791864000))
    assert log.launches == (Launch("Plan", "opus"), Launch("surface-extractor", None))


def test_a_killed_session_has_no_result_and_a_cut_line_is_passed_over(tmp_path: Path) -> None:
    path = stream(tmp_path / "killed.jsonl", cost=None, gauges=(0.2,))
    with path.open("a", encoding="utf-8") as out:
        out.write('{"type": "assistant", "message": {"cont')
    log = read_log(path)
    assert not log.ended
    assert log.final == ""
    assert log.cost == 0
    # A reading the stream does not date belongs to no week it can name.
    assert log.gauges == (Gauge(0.2, None),)


def test_what_a_session_must_never_read_is_found_in_its_tool_calls(tmp_path: Path) -> None:
    clean = stream(tmp_path / "clean.jsonl", reads=("/out/work/lending/lending/loans.py",))
    peeked = stream(tmp_path / "peeked.jsonl", reads=("/clone/evals/cases/01/brief.md",))
    needles = ("/clone/", "evals/cases")
    assert named_in_tool_calls(clean, needles) == []
    assert named_in_tool_calls(peeked, needles) == ["/clone/", "evals/cases"]


def test_no_session_starts_outside_the_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(toy.CONTAINER, raising=False)
    with pytest.raises(toy.OutsideContainerError):
        run_chain(tmp_path, "/surface-execute", tmp_path / "log.jsonl")
    with pytest.raises(toy.OutsideContainerError):
        ask(
            "A question?",
            tmp_path / "ask.jsonl",
            system="You answer.",
            model="sonnet",
            cwd=tmp_path,
        )
