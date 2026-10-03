"""The corpus: the host, the cases, and what proves their acceptance tests fair (evals/cases/)."""

import json
import shutil
from pathlib import Path

import pytest

from surface_evals import CASES, HOST
from surface_evals.corpus import (
    KEYS,
    SHAPES,
    CaseError,
    apply_reference,
    copy_host,
    load_case,
    load_cases,
    run_acceptance,
)
from surface_evals.measure import ZONES
from surface_evals.runner import GATE, gate_passes

NAMES = sorted(path.name for path in CASES.iterdir() if (path / "case.json").is_file())


def test_the_corpus_holds_one_case_per_shape() -> None:
    cases = load_cases()
    assert [case.name for case in cases] == NAMES
    assert sorted(case.shape for case in cases) == sorted(SHAPES)
    for case in cases:
        assert case.need
        assert case.brief
        assert "## Not mine to decide" in case.brief


def test_the_host_passes_the_gate_it_states(tmp_path: Path) -> None:
    project = tmp_path / "lending"
    copy_host(project)
    assert GATE in (HOST / "AGENTS.md").read_text(encoding="utf-8")
    assert gate_passes(project)


@pytest.mark.parametrize("name", NAMES)
def test_the_acceptance_tests_fail_on_the_host_and_pass_on_the_reference(
    name: str, tmp_path: Path
) -> None:
    (case,) = load_cases([name])
    project = tmp_path / "lending"
    copy_host(project)
    untouched = run_acceptance(case, project)
    # The feature is not there: tests that passed anyway would prove nothing.
    assert untouched.ran > 0
    assert untouched.failed > 0, untouched.output
    apply_reference(case, project)
    built = run_acceptance(case, project)
    assert built.ok, built.output
    assert built.ran == untouched.ran
    # The reference is a change the host would take: its own tests still pass.
    assert gate_passes(project)


def test_the_host_never_names_the_evaluations() -> None:
    for path in HOST.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            text = path.read_text(encoding="utf-8").lower()
            assert "acceptance" not in text, path
            assert "evals" not in text, path


def test_a_case_names_only_the_zones_the_host_declares_and_files_it_holds() -> None:
    for case in load_cases():
        assert set(case.critical_zones) <= set(ZONES), case.name
        assert bool(case.critical_zones) == bool(case.critical_files), case.name
        for path in case.critical_files:
            assert (HOST / path).is_file(), path
    touched = [case.name for case in load_cases() if case.critical_zones]
    assert touched, "no case touches a critical zone"


def test_one_case_carries_an_amendment_so_that_a_revision_is_drawn() -> None:
    amended = [case for case in load_cases() if case.amendment is not None]
    assert [case.shape for case in amended] == ["several-flows"]


def test_a_case_that_is_not_whole_is_refused(tmp_path: Path) -> None:
    def broken(name: str) -> Path:
        copy = tmp_path / name
        shutil.copytree(CASES / NAMES[0], copy)
        return copy

    without_brief = broken("no-brief")
    (without_brief / "brief.md").unlink()
    with pytest.raises(CaseError, match=r"brief\.md is missing"):
        load_case(without_brief)

    raw = json.loads((CASES / NAMES[0] / "case.json").read_text(encoding="utf-8"))
    assert tuple(raw) == KEYS
    for name, change, message in (
        ("shape", {"shape": "enormous"}, "unknown shape"),
        ("sections", {"body_sections": {"min": 3, "max": 1}}, "body_sections"),
        ("diagram", {"diagram": "many"}, "diagram must be one of"),
        ("zones", {"critical_zones": "fines"}, "critical_zones must be a list"),
    ):
        folder = broken(name)
        (folder / "case.json").write_text(json.dumps({**raw, **change}), encoding="utf-8")
        with pytest.raises(CaseError, match=message):
            load_case(folder)
    missing_key = broken("key")
    (missing_key / "case.json").write_text(
        json.dumps({key: value for key, value in raw.items() if key != "amendment"}), "utf-8"
    )
    with pytest.raises(CaseError, match="exactly the keys"):
        load_case(missing_key)


def test_an_unknown_case_is_refused_with_the_names_of_those_known() -> None:
    with pytest.raises(CaseError, match=NAMES[0]):
        load_cases(["no-such-case"])
