"""The questions a developer hands back (evals/surface_evals/developer.py)."""

import pytest

from surface_evals.developer import RULES, YOUR_CALL, hands_back


def test_the_rules_give_the_words_a_question_handed_back_is_read_from() -> None:
    assert YOUR_CALL.search(RULES) is not None


# As the answers kept from the campaigns say it, the third with the apostrophe a model may type.
@pytest.mark.parametrize(
    "said",
    [
        "That's the assistant's call, since the order of the checks isn't mine to decide.",
        "That's your call, and I'm going with your recommendation, A: ignore it silently.",
        "That\u2019s the assistant\u2019s call, and I'm fine with its recommendation, A.",
        # In part: the answer settles what the developer knows, and leaves the rest.
        "There are only the two categories. What happens with a bad value is your call.",
    ],
)
def test_an_answer_that_leaves_the_question_to_the_assistant_hands_it_back(said: str) -> None:
    assert hands_back(said) is True


@pytest.mark.parametrize(
    "said",
    [
        "C. A student can hold at most 3 books, and staff can hold at most 6.",
        # A recommendation agreed with is an answer: only the words of the rules hand back.
        "A. An extra argument gets the usual usage error, so I'm fine with your recommendation.",
        "Nothing to add.",
    ],
)
def test_an_answer_that_decides_hands_nothing_back(said: str) -> None:
    assert hands_back(said) is False
