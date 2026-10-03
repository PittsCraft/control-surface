"""The judge and its rubric (evals/surface_evals/judge.py, evals/judge/)."""

import json
from pathlib import Path

import pytest
from support import case, kept_run

from surface_evals import judge_check
from surface_evals.judge import (
    Dimension,
    JudgeError,
    documents_of,
    load_rubric,
    parse,
    prompt,
    timeline,
)

DOCUMENTS = {"need": "List the overdue loans.", "blueprint": "It prints one line per late loan."}
DIMENSION = Dimension(
    id="blueprint",
    title="the blueprint",
    text="## blueprint: the blueprint\n\n- **decidable**: nothing is missing.",
    reads=("need", "blueprint"),
    code=False,
    criteria=("decidable", "no-padding"),
)


def _answer(*judgements: dict[str, object]) -> str:
    return "Here is my judgement.\n" + json.dumps({"judgements": list(judgements)})


def test_the_rubric_holds_the_two_questions_of_working_with_the_chain() -> None:
    system, dimensions = load_rubric()
    assert "a score, a whole number from 1 to 5" in system
    assert "3: one clear lapse. 2: several clear lapses." in system
    assert "copied word for word from one of the documents" in system
    assert [dimension.id for dimension in dimensions] == [
        "blueprint",
        "interview",
        "messages",
        "following",
    ]
    by_id = {dimension.id: dimension for dimension in dimensions}
    assert by_id["blueprint"].criteria == ("decidable", "no-padding", "cut", "diagrams")
    assert by_id["interview"].criteria == (
        "questions-matter",
        "not-already-answered",
        "no-invented-rule",
        "right-number",
    )
    assert by_id["messages"].criteria == ("clear", "right-length", "next-step")
    assert by_id["following"].criteria == ("whose-turn", "why-stopped", "no-noise")
    # Only the interview is judged against the code: whether a question was already answered.
    assert [dimension.id for dimension in dimensions if dimension.code] == ["interview"]
    assert by_id["interview"].reads == ("need", "interview", "blueprint")
    assert by_id["following"].reads == ("stops",)


def test_the_judge_is_given_its_part_of_the_rubric_and_the_documents_it_names() -> None:
    asked = prompt(DIMENSION, DOCUMENTS)
    assert asked.startswith(DIMENSION.text)
    assert '<document name="need">\nList the overdue loans.\n</document>' in asked
    assert "One JSON object and nothing else" in asked
    assert "(decidable, no-padding)" in asked
    assert "your working directory" not in asked
    with_code = prompt(
        Dimension("interview", "it", "## interview: it", ("need",), code=True, criteria=("a",)),
        DOCUMENTS,
    )
    assert "as it was before the feature, is in your working directory" in with_code


def test_a_judgement_keeps_its_reason_and_whether_its_passage_is_in_a_document() -> None:
    answer = _answer(
        {
            "criterion": "decidable",
            "score": 4,
            "reason": "The order of the lines is not said.",
            "passage": "It prints one line\nper late loan.",
        },
        {"criterion": "no-padding", "score": "5", "reason": "Short.", "passage": "made up"},
    )
    first, second = parse(answer, DIMENSION, DOCUMENTS)
    # A score written as a text is read as the number it is.
    assert second.score == 5
    assert (first.dimension, first.criterion, first.score) == ("blueprint", "decidable", 4)
    assert first.reason == "The order of the lines is not said."
    assert first.grounded
    assert not second.grounded


@pytest.mark.parametrize(
    "answer",
    [
        "I cannot judge this.",
        _answer({"criterion": "decidable", "score": 4, "reason": "", "passage": ""}),
        _answer(
            {"criterion": "decidable", "score": 6, "reason": "", "passage": ""},
            {"criterion": "no-padding", "score": 5, "reason": "", "passage": ""},
        ),
        _answer(
            {"criterion": "decidable", "score": "high", "reason": "", "passage": ""},
            {"criterion": "no-padding", "score": 5, "reason": "", "passage": ""},
        ),
    ],
)
def test_an_answer_that_is_not_a_judgement_of_each_criterion_is_refused(answer: str) -> None:
    with pytest.raises(JudgeError):
        parse(answer, DIMENSION, DOCUMENTS)


def test_the_judge_reads_a_run_as_the_developer_lived_it(tmp_path: Path) -> None:
    stops = [
        {"kind": "need", "said": "x" * 700, "state": "interview", "final": "Q1?", "ended": True},
        {
            "kind": "answer",
            "said": "A.",
            "state": "awaiting-approval",
            "final": "Read it.",
            "ended": True,
        },
    ]
    (tmp_path / "need.md").write_text("List the overdue loans.\n", encoding="utf-8")
    root = kept_run(tmp_path, journal=[], stops=stops)
    documents = documents_of(root, case(tmp_path))
    assert set(documents) == {"need", "stops", "interview", "blueprint", "pr-body"}
    told = documents["stops"]
    assert "### Stop 1" in told
    assert "The developer said (need):" in told
    assert "x" * 600 + " [...]" in told
    assert "in the state `awaiting-approval`, on this message:\n\nRead it." in told
    assert told == timeline({"stops": stops})


def test_each_spoiled_document_lowers_a_criterion_of_the_rubric_and_differs_from_its_original() -> (
    None
):
    _, dimensions = load_rubric()
    criteria = {dimension.id: dimension.criteria for dimension in dimensions}
    reads = {dimension.id: dimension.reads for dimension in dimensions}
    originals = judge_check.originals()
    pairs = judge_check.load_pairs()
    # The three the evaluation asks for: a padded blueprint, one stripped of a decision, an
    # interview with a question already answered.
    assert [(pair.dimension, pair.criterion) for pair in pairs] == [
        ("blueprint", "no-padding"),
        ("blueprint", "decidable"),
        ("interview", "not-already-answered"),
    ]
    for pair in pairs:
        assert pair.criterion in criteria[pair.dimension]
        assert pair.replaces in reads[pair.dimension]
        assert pair.spoiled != originals[pair.replaces]
    padded, stripped, answered = (pair.spoiled for pair in pairs)
    assert len(padded) > len(originals["blueprint"]) > len(stripped)
    assert "An empty shelf prints the header alone" not in stripped
    assert answered.count("### Q") == originals["interview"].count("### Q") + 2
