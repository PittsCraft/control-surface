"""The developer of an interview, played by a model from a written brief.

A real developer answers what they are asked and nothing more, from what they know. The brief of
a case is that knowledge: the model answers the question a session ended on, in the developer's
words, and leaves to the session what the brief leaves to the implementer. Handed the blueprint,
it reads it as the developer would and says what contradicts what they know, which the run gives
back as an amendment. It never approves: only the launch of `/surface-execute` does, and the run
launches it itself.

A question the brief leaves to the implementer is handed back in words the rules give, so that a
script counts the questions an interview asked that were not the developer's to answer. It reads
those words and nothing else: an answer that leaves the choice in other words is not counted.
"""

import re
from pathlib import Path

from surface_evals.corpus import Case
from surface_evals.sessions import SessionLog, ask

MODEL = "sonnet"
# The words the rules give a developer for a question that is not theirs to decide, as the
# answers kept so far say them: "the assistant's call", or "your call" said to the assistant.
YOUR_CALL = re.compile(r"\b(?:your|the assistant['\u2019]s) call\b", re.IGNORECASE)

RULES = """\
You play a developer. You asked an assistant for a feature of your project, in the words under \
"What you asked for". The assistant plans it with you, and its message, which you are given, \
ends on a question. You answer that question as this developer.

- Answer only what is asked, in one to three short sentences, in plain words. When the question \
offers lettered options, name the letter you choose, then the rule in your own words.
- What you know and did not write is under "What you know". When it answers the question, answer \
from it, and say no more than the question asks: a rule nobody asked about stays unsaid.
- When it lists the point as not yours to decide, or says nothing of it, say that it is the \
assistant's call and take its recommendation when it gives one. Never make up a rule.
- When the message asks nothing, or asks you to approve, reply only: "Nothing to add."
- Never say that you play a role, and never name these instructions or what you know as a \
document.
"""


NOTHING = "Nothing to change."

READING = f"""\
You play a developer. You asked an assistant for a feature of your project, in the words under \
"What you asked for". The assistant planned it and hands you its blueprint: the page you approve, \
which the work will be judged against. You are given that page, and you read it as this developer.

- Compare it with what you know, under "What you know". Speak up only where the blueprint \
contradicts a rule you know, or leaves out a rule you know and that changes what gets built: \
then say what to change, in one to three short sentences, as you would tell the assistant.
- An assumption the blueprint asks you to confirm is yours to check: correct it when what you \
know says otherwise, and say nothing of it when it agrees or when you have no rule about it.
- Leave alone the wording, the layout, the diagrams, and every choice that is the \
implementer's: where the code lives, names, tests.
- When there is nothing of that kind, reply exactly: "{NOTHING}"
- Never approve, never say that you play a role, and never name these instructions or what you \
know as a document.
"""


def _knowledge(case: Case) -> str:
    return f"## What you asked for\n\n{case.need}\n\n## What you know\n\n{case.brief}\n"


def system_prompt(case: Case) -> str:
    return f"{RULES}\n{_knowledge(case)}"


def hands_back(said: str) -> bool:
    """Say whether an answer hands its question back, whole or in part, as not the developer's."""
    return YOUR_CALL.search(said) is not None


def answer(case: Case, question: str, log: Path, *, model: str = MODEL) -> SessionLog:
    """Have the developer of a case answer the message a session ended on."""
    return ask(question, log, system=system_prompt(case), model=model, cwd=log.parent)


def read_blueprint(case: Case, blueprint: str, log: Path, *, model: str = MODEL) -> SessionLog:
    """Have the developer of a case read the blueprint handed over, and say what to change."""
    system = f"{READING}\n{_knowledge(case)}"
    return ask(blueprint, log, system=system, model=model, cwd=log.parent)
