"""The judge and its rubric (evals/surface_evals/judge.py, evals/judge/)."""

import json
from pathlib import Path

import pytest
from support import case, kept_run, stream

from surface_evals import judge, judge_check
from surface_evals.budget import Ledger
from surface_evals.judge import (
    IN_PLANNING,
    STOPPED_AT_HAND_OVER,
    Dimension,
    JudgeError,
    documents_of,
    in_planning,
    judge_run,
    load_rubric,
    parse,
    prompt,
    timeline,
)
from surface_evals.runner import STOPPED
from surface_evals.sessions import SessionLog, read_log

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


def test_the_rubric_does_not_fault_what_the_chain_does_on_purpose() -> None:
    _, dimensions = load_rubric()
    criteria = {
        f"{dimension.id}.{line.split('**')[1]}": line
        for dimension in dimensions
        for line in dimension.text.splitlines()
        if line.startswith("- **")
    }
    # What the frame of a blueprint asks for is not padding, and a diagram may draw the prose.
    padding = criteria["blueprint.no-padding"]
    assert "Three things the frame of a blueprint asks for are not padding" in padding
    for asked in ("the closing line", "the statement of the critical zones", "the boundaries"):
        assert asked in padding
    # Bare lines only: the rule of a zone told again in full is still a fact said twice.
    assert "The first two are bare lines, and say no fact twice" in padding
    assert "the rule of a zone told again in full still does" in padding
    assert "Nor is a diagram that draws what the prose says a fact said twice" in padding
    # A chain with a single fork is no shape; where the shape is real, the prose may say it too.
    diagrams = criteria["blueprint.diagrams"]
    assert "a chain with no branch or a chain with a single fork" in diagrams
    assert "a diagram may draw what the prose already says: do not fault it for that" in diagrams
    # The words the README and the guide teach are the developer's; the insides are named.
    clear = criteria["messages.clear"]
    assert "The words of the chain that its README and its guide teach are the developer's" in clear
    for word in ("its cut", "the gates", "the critical zones", "a slice", "the cross-check"):
        assert word in clear
    assert "The insides are the name of any agent but the reviewer" in clear
    assert "and the paths of its reports: a final message keeps them out" in clear
    assert "Neither the blueprint nor a plan change proposal is a report" in clear
    # The description is the script's, which links the reports it lists: none is faulted there.
    assert "The description of the pull request is written by a script" in clear
    # The launch that approves, said at every hand over, is the point.
    noise = criteria["following.no-noise"]
    said = "One thing said at every hand over, and in reply to a sentence that agrees, is not"
    assert f"{said} noise" in noise
    assert "that only the launch of `/surface-execute` approves" in noise
    # The hand back at conformity is one line: conformant says the rest, and no account is owed.
    length = criteria["messages.right-length"]
    assert "a stop that ended in the state `conformant` is short on purpose" in length
    assert "names the files `pr-body` lists under the critical zones, when it lists any" in length
    assert "so the developer needs no account of the run: do not fault that message" in length
    assert "Fault it when one of the three is missing" in length
    # At that stop, the word conformant is the reason.
    stopped = criteria["following.why-stopped"]
    assert "a message that says the plan is conformant has said why, the work done" in stopped
    assert "The developer knows the word from the guide of the chain" in stopped
    assert "Do not ask that message to say it in other words, nor for what was built" in stopped


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


def test_a_dimension_that_reads_the_stops_is_asked_of_planning_when_the_run_stopped() -> None:
    _, dimensions = load_rubric()
    by_id = {dimension.id: dimension for dimension in dimensions}
    # The interview and the blueprint are whole at the hand over: the rubric as written.
    for name in ("blueprint", "interview"):
        assert in_planning(by_id[name]) == by_id[name]
    # The stops and the pull request description go no further than planning: the judge is told
    # so, and judges the same criteria on the same documents under another name.
    for name in ("messages", "following"):
        dimension = by_id[name]
        planned = in_planning(dimension)
        assert planned.id == f"{name}{IN_PLANNING}"
        assert planned.text == f"{dimension.text}\n\n{STOPPED_AT_HAND_OVER}"
        assert (planned.reads, planned.criteria, planned.code) == (
            dimension.reads,
            dimension.criteria,
            dimension.code,
        )
        assert f"{STOPPED_AT_HAND_OVER}\n\n## The documents" in prompt(
            planned, dict.fromkeys(planned.reads, "x")
        )


def test_the_verdicts_of_a_run_that_stopped_at_the_hand_over_never_take_the_names_of_a_whole_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def ask(question: str, log: Path, **_: object) -> SessionLog:
        """Play the judge: a 4 on each criterion the question names."""
        asked.append(question)
        named = question.rsplit(" rubric (", 1)[1].split(")", 1)[0].split(", ")
        given = [{"criterion": name, "score": 4, "reason": "", "passage": ""} for name in named]
        return read_log(stream(log, final=json.dumps({"judgements": given})))

    _, dimensions = load_rubric()

    def judged(root: Path) -> set[str]:
        """Judge a run, and name the dimensions its verdicts are kept under."""
        ledger = Ledger.load(root, max_usd=None, max_points=None)
        verdicts = judge_run(root, case(tmp_path), model="opus", repeats=1, ledger=ledger)
        kept = json.loads(verdicts.read_text(encoding="utf-8"))
        assert kept["refused"] == []
        # Every criterion of the rubric is judged, whatever the run.
        assert len(kept["judgements"]) == sum(len(dimension.criteria) for dimension in dimensions)
        return {item["dimension"] for item in kept["judgements"]}

    monkeypatch.setattr(judge, "ask", ask)
    (tmp_path / "need.md").write_text("List the overdue loans.\n", encoding="utf-8")
    stopped = kept_run(
        tmp_path / "stopped", journal=[], outcome=STOPPED, stops=[], stop_at_hand_over=True
    )
    names = judged(stopped)
    assert {"blueprint", "interview", f"messages{IN_PLANNING}", f"following{IN_PLANNING}"} <= names
    assert names.isdisjoint({"messages", "following"})
    # The judge is asked in the order of the rubric, and told of the stop where it reads the stops.
    told = {
        dimension.id: STOPPED_AT_HAND_OVER in question
        for dimension, question in zip(dimensions, asked, strict=True)
    }
    assert (told["blueprint"], told["interview"]) == (False, False)
    assert (told["messages"], told["following"]) == (True, True)
    assert (stopped / "logs-judge" / f"messages{IN_PLANNING}-01.jsonl").is_file()
    # A run played whole is asked the rubric as written, under its names.
    asked.clear()
    whole = kept_run(tmp_path / "whole", journal=[], stops=[])
    assert judged(whole) == {dimension.id for dimension in dimensions}
    assert not any(STOPPED_AT_HAND_OVER in question for question in asked)


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
        original = judge_check.documents(pair, spoiled=False)
        spoiled = judge_check.documents(pair, spoiled=True)
        # One document differs, the one the pair spoils.
        assert [name for name in original if original[name] != spoiled[name]] == [pair.replaces]
    padded, stripped, answered = (pair.spoiled for pair in pairs)
    # The padded blueprint is its own lean original with padding added, nothing taken away.
    lean = pairs[0].original
    assert lean is not None
    assert all(line in padded for line in lean.splitlines())
    assert len(padded) > 2 * len(lean)
    assert pairs[1].original is None
    assert len(originals["blueprint"]) > len(stripped)
    assert "An empty shelf prints the header alone" not in stripped
    assert answered.count("### Q") == originals["interview"].count("### Q") + 2
