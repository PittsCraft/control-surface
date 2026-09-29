"""The index of the decisions lists every ADR, under its own title."""

from prompt_support import ROOT

ADR = ROOT / "docs" / "adr"


def test_the_index_lists_every_decision_under_its_title() -> None:
    index = (ADR / "README.md").read_text(encoding="utf-8")
    for path in sorted(ADR.glob("0*.md")):
        number, _, title = (
            path.read_text(encoding="utf-8").splitlines()[0].removeprefix("# ").partition(". ")
        )
        assert f"| {number} | [{title}]({path.name}) |" in index, path.name
