# 0036. Evaluations on real sessions, with a model as the developer and a judge that is checked

Status: accepted
Date: 2026-10-03

## Context

The tests hold three things: the state script, the wording of the prompts, and, end to end, that a real session reaches the expected state on a toy with one behavior (ADR 0025). None says whether the chain delivers what the README promises, nor whether its documents and its messages serve the developer who works with it. A change of the blueprint's form showed the gap: a body cut in several sections and a diagram drawn under the new rule were never observed, and a hand over that described the wrong thing was found only because someone read the session.

Such questions have no assertion to write. A blueprint that hides nothing, a review that classifies a fault right, an interview that frames a need are seen on real sessions only, on needs of several shapes, more than once since a model does not take the same path twice, and some of it is a judgement.

## Decision

An evaluation run on demand, on real sessions and with no human in it, under `evals/`. It evaluates what the chain adds, not what the model does well alone: the detailed plan is left out.

- **A synthetic host**, `evals/host/`, written for the purpose rather than a real repository: it has what the cases need, several components, state, two declared critical zones, and nothing else, it costs nothing to build, it never drifts, and it raises no question of licence or of privacy.
- **A corpus chosen for its shapes**, one need each: one behavior, several flows, one flow across components, a trade-off, a critical zone touched, an ambiguous need. Each case keeps from the agents the acceptance tests of the delivered code, and a reference implementation that proves those tests fair, which the unit tests check.
- **A model plays the developer**, from a written brief of what the developer knows and did not write. Written answers alone cannot meet questions that change from one run to the next. The model answers what is asked and nothing more, then reads the blueprint handed over and corrects what contradicts the brief, as a developer would: a rule the interview did not ask for costs a correction when the blueprint shows the guess, and an acceptance test when it does not. It never approves: the run launches `/surface-execute` itself.
- **What a script can measure, a script measures**, from the journal, the plan folder, the streams and the delivered code: the outcome, the passes, the acceptance, the critical zones, the form of the blueprint. Faults put there on purpose, on the toy, show whether the cross-check finds what a blueprint hides and whether the review classifies a defect, a deviation and a break.
- **The rest is judged by a model against a written rubric**, each judgement with its reason and the passage it rests on. The judge is itself checked without a human: documents spoiled in a known way must score below their originals, and a passage that stands in no document is marked.
- **No threshold, and not in CI.** A measure is kept as its spread over the runs, and the report says what lies outside the spread of the campaign before. What to hold is decided once the measures have been observed.

The sessions are those of the end to end tests: headless, permissions bypassed, in the same container, where they refuse to start otherwise.

## Consequences

A campaign costs dollars and hours, and its cost is watched: a ledger sums the list price of the sessions and the rise of the subscription's weekly gauge, and a command stops before a ceiling. The corpus is small and synthetic: it says nothing of a large code base, and a case whose acceptance tests are wrong blames the chain for nothing, which the reference implementations guard against. The judge is a model: its scores are read as a trend between two versions of the prompts, on the criteria its check clears, never as a grade. The sessions can read the clone the container mounts, where the cases are: a run that does is marked rather than prevented. The report compares versions only as far as the campaigns were kept, under `evals/reports/`, by whoever ran them.
