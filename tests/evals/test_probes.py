"""The faults put there on purpose, built without a session (evals/surface_evals/probes.py)."""

from pathlib import Path

import pytest
import toy

from surface_evals import probes
from surface_evals.blueprint import NONE_TOUCHED, parse
from surface_evals.probes import CHECKER_PROBES, CLASSES, REVIEWER_PROBES
from surface_evals.runner import state_of
from surface_status.plan_folder import parse_gates, parse_slice_markers


def test_one_faithful_blueprint_and_three_that_hide_what_matters() -> None:
    assert [probe.hides for probe in CHECKER_PROBES] == [False, True, True, True]
    faithful, column, zone, effect = CHECKER_PROBES
    assert (faithful.plan(), faithful.blueprint()) == (toy.PLAN, toy.BLUEPRINT)
    # Each spoiled probe changes one document and leaves the other as written.
    assert column.blueprint() == toy.BLUEPRINT
    assert "`title,author,year,isbn`" in column.plan()
    assert zone.plan() == toy.PLAN
    assert NONE_TOUCHED.search(parse(zone.blueprint()).zones)
    assert effect.blueprint() == toy.BLUEPRINT
    assert "rewrites the shelf file" in effect.plan()
    for probe in CHECKER_PROBES:
        assert parse_slice_markers(probe.plan()) == (1, 2)
        assert parse_gates(probe.plan()) == (toy.GATE_COMMAND,)
        assert parse(probe.blueprint()).framed


def test_a_probe_built_on_a_text_the_toy_no_longer_holds_says_so() -> None:
    with pytest.raises(ValueError, match="stale"):
        probes.swap(toy.PLAN, "a sentence the toy never held", "anything")


def test_the_cross_check_probe_waits_in_a_plan_folder_being_drafted(tmp_path: Path) -> None:
    project, plan = probes.drafting(tmp_path, CHECKER_PROBES[1])
    assert state_of(project) == "drafting"
    assert (project / plan / "blueprint.md").read_text(encoding="utf-8") == toy.BLUEPRINT
    assert "isbn" in (project / plan / "plan.md").read_text(encoding="utf-8")
    assert not (project / plan / "checks").exists()
    assert toy.git(project, "status", "--porcelain").strip() == ""


def test_the_review_probes_cover_work_as_planned_and_each_class_of_finding() -> None:
    assert [probe.fault for probe in REVIEWER_PROBES] == [None, "defects", "deviations", "breaks"]
    assert CLASSES == ("deviations", "defects", "breaks")
    assert {probe.state for probe in REVIEWER_PROBES} == {
        toy.State.DONE,
        toy.State.DEFECT,
        toy.State.DEVIATION,
        toy.State.DEVELOPER_BREAK,
    }
