"""The command line of the evaluations (evals/surface_evals/cli.py, evals/run.py)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import toy

from surface_evals import cli
from surface_evals.report import REPORT, SUMMARY
from surface_evals.runner import Run

RUN = Path(__file__).resolve().parents[2] / "evals" / "run.py"


def test_the_report_of_an_empty_campaign_says_so_and_starts_no_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--out", str(tmp_path), "report"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / REPORT)
    summary = json.loads((tmp_path / SUMMARY).read_text(encoding="utf-8"))
    assert summary["cases"] == {}
    assert summary["all"]["runs"] == 0
    assert "0 runs over 0 cases" in (tmp_path / REPORT).read_text(encoding="utf-8")


def test_a_kept_report_goes_under_the_reports_of_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPORTS", tmp_path / "reports")
    assert cli.main(["--out", str(tmp_path / "campaign"), "report", "--keep"]) == 0
    (kept,) = (tmp_path / "reports").iterdir()
    chain = json.loads((kept / SUMMARY).read_text(encoding="utf-8"))["chain"]
    assert kept.name.endswith(f"-{chain}")
    assert (kept / REPORT).is_file()


def test_the_corpus_starts_no_session_outside_the_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(toy.CONTAINER, raising=False)
    with pytest.raises(toy.OutsideContainerError):
        cli.main(["--out", str(tmp_path), "corpus", "--case", "01-overdue-list"])
    # The project of the run was built, and nothing was said in it.
    record = tmp_path / "runs" / "01-overdue-list" / "run-01"
    assert (record / "work" / "lending" / "lending" / "fines.py").is_file()
    assert not (record / "logs").exists() or not list((record / "logs").glob("*.jsonl"))


def test_the_corpus_tells_its_runs_to_stop_at_the_hand_over_only_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    told: list[bool] = []

    def play(run: Run) -> str:
        told.append(run.stop_at_hand_over)
        return run.root.name

    monkeypatch.setattr(cli, "_play", play)
    corpus = ["--out", str(tmp_path), "corpus", "--case", "01-overdue-list"]
    assert cli.main(corpus) == 0
    assert cli.main([*corpus, "--stop-at-hand-over"]) == 0
    assert told == [False, True]
    # The other options hold: the second run takes the next folder of the same case.
    assert capsys.readouterr().out.split() == ["run-01", "run-02"]


def test_the_script_finds_the_harness_from_any_folder(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(RUN), "--out", str(tmp_path / "campaign"), "report"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "campaign" / REPORT).is_file()


def test_an_unknown_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as stopped:
        cli.main(["measure"])
    assert stopped.value.code == 2
