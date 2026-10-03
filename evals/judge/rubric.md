# Rubric

You judge how a chain of agents served a developer. The developer described a need, answered an interview, read one page, the blueprint, and approved it; agents then built the feature and reviewed it against that page. The developer reads the blueprint and what the sessions tell them. They read neither the detailed plan nor the code. You are given documents of one such run, and one aspect to judge, with its criteria.

Judge what is in the documents, as this developer would live it. Do not judge the feature, the code, or what you would have built.

For each criterion, give:

- a score, a whole number from 1 to 5. 5: it holds throughout, with no lapse. 4: one lapse of detail. 3: one clear lapse. 2: several clear lapses. 1: the lapses outweigh the rest, and the documents fail the criterion as a whole.
- a reason, two sentences at most, that names the lapse or says why there is none.
- a passage, copied word for word from one of the documents: the place where the lapse is, or, for a 5, the place that shows best that the criterion holds. For something missing, the place where it should have stood.

Be strict: a 5 is earned, and a document that is merely plausible gets a 3. Do not reward length.

## blueprint: the blueprint, for a developer who must decide

Reads: `need`, `interview`, `blueprint`

The blueprint is the page the developer approves, then the contract the work is judged against. They read all of it. Is this the level of precision they need to decide?

- **decidable**: nothing is missing to decide. Every rule, visible behavior, data shape and irreversible effect the feature brings is stated, with the answers of the interview carried, so that the developer has nothing to guess and no other file to open.
- **no-padding**: nothing they would skip. No fact said twice, no detail of implementation that is not theirs to decide, no section or diagram that is there for its own sake, no restating of the need without adding to it.
- **cut**: the body is cut by what the developer decides separately, one section for one behavior, otherwise by flow, by component or by decision, with titles in the words of the feature and in the order they would discover it.
- **diagrams**: a diagram stands where what it shows has a shape that prose flattens, several things in relation, an order between actors, states and transitions, a path that branches, and nowhere else: not for a single fact, a list or a chain with no branch.

## interview: the interview, which frames the need

Reads: `need`, `interview`, `blueprint`, `code`

Before planning, a session asked the developer what the need left open, one question at a time. Did the interview frame the need?

- **questions-matter**: each question changes what gets built, and is one only the developer can answer: a business rule, a visible behavior, a contract with someone else.
- **not-already-answered**: no question asks what the need already says, or what the code of the project already settles. Check the code before you fault a question, and before you clear one.
- **no-invented-rule**: no business rule was decided without the developer. Every rule the blueprint states comes from the need, from an answer, or from the code; one that comes from none of them was invented, unless the blueprint gives it to the developer as an assumption to confirm.
- **right-number**: as many questions as the need calls for. None is missing, where a gap was filled by a guess, and none is there to be thorough.

## messages: what the agents say

Reads: `stops`, `pr-body`

`stops` tells the run in order: what the developer said, the state of the plan when the session it went to ended, and the final message of that session, which is all the developer sees of it. `pr-body` is the pull request description the chain keeps. Judge the final messages and the description.

- **clear**: each message says what happened in words the developer can act on, without the vocabulary of the chain's insides, and nothing in it contradicts the state the plan is in.
- **right-length**: each message is as long as what it has to say. Nothing the developer needs is left out, and nothing is repeated from a file they are sent to read.
- **next-step**: each message ends on what the developer does next, and that step is the right one for the state the plan is in.

## following: following along

Reads: `stops`

Read `stops` as the developer who lived the run and nothing else.

- **whose-turn**: at every stop, the developer knows whether it is their turn, and what is expected of them.
- **why-stopped**: every stop says why the session stopped there: a question, a hand over, a hand back with its reason, the work done.
- **no-noise**: nothing is told that the developer does not need: steps of the chain narrated for their own sake, the same fact at several stops, reassurance.
