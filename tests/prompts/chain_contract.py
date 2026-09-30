"""The contract of the chain that the prompts must carry, stated once for the prompt tests.

The state script holds its own contract in code. The prompts hold theirs in prose, so the tests
state here what the chain promises a developer, and check that each prompt says it: how a review
classifies a finding, which command acts on a plan in each state, which acts of the developer each
command takes in the conversation, in which order planning records its events and the execution
loop reads its rows, what the reviewer writes, the sections of an overview, and the language of
the plan documents.
"""

# A review classifies a finding by two closed questions, in this order. A yes to the first is a
# contract break; otherwise a yes to the second is a defect, the code is fixed, and a no a
# deviation, the plan is amended.
BREAK_QUESTION = "Must the overview be modified for it to stay true?"
DEFECT_QUESTION = "Must the code be fixed?"
# A review with no finding ends the loop in this state.
NO_FINDING_END = "conform state"
# On conform, the loop hands back in one line. A criterion the reviewer cannot prove is a finding,
# so conform leaves nothing to check: `conformity.md` is kept, never a required reading. The chain
# never marks the pull request ready, since that triggers the host's CI.
CONFORM_HAND_BACK = (
    "the plan is conform, and the developer marks the pull request ready when they want"
)

# The commands that act on a plan in each state where work remains. The other command does not
# see the plan: it neither resumes it nor offers it.
PLAN = "surface-plan"
EXECUTE = "surface-execute"
SEEN_BY: dict[str, frozenset[str]] = {
    "interview": frozenset({PLAN}),
    "drafting": frozenset({PLAN}),
    "awaiting-approval": frozenset({PLAN, EXECUTE}),
    "executing": frozenset({EXECUTE}),
    "reviewing": frozenset({EXECUTE}),
    "fixing": frozenset({EXECUTE}),
    "plan-change-proposed": frozenset({PLAN, EXECUTE}),
    "blocked": frozenset({PLAN, EXECUTE}),
}

# The acts of the developer each command takes in the conversation, without a new launch, as
# (command, the state it records from, the event). None of them approves a revision: only the
# launch of `/surface-execute` does. An accepted plan change and an amendment at the execution
# ceiling go to `/surface-plan`, which alone writes the plan.
IN_CONVERSATION = (
    (PLAN, "awaiting-approval", "amendment-received"),
    (PLAN, "blocked", "resumed"),
    (EXECUTE, "plan-change-proposed", "plan-change-refused"),
    (EXECUTE, "plan-change-proposed", "plan-change-accepted"),
    (EXECUTE, "blocked", "resumed"),
)

# The events `/surface-plan` records on a first launch, in the order it records them.
PLANNING_EVENTS = ("plan-opened", "interview-closed", "check-done", "plan-drafted")

# The rows of the loop of `/surface-execute`, as it words them, in the order it must read them:
# the first row that holds wins. The two rows marked "at launch" record an act of the developer.
EXECUTION_LOOP = (
    "`awaiting-approval`, at launch",
    "`blocked` during execution, at launch",
    "`plan-change-proposed`",
    "`conform`, `abandoned`",
    "Ceiling reached, and work left to the agents",
    "`executing`, a break suspected",
    "`executing`",
    "`reviewing`, the last event a clean review, nothing changed since",
    "`reviewing`, no green gate run since the last change",
    "`reviewing`, gates green",
    "`fixing`",
)

# The files of a plan folder the reviewer writes.
REVIEWER_WRITES = (
    "reviews/pass-NN.md",
    "reviews/suspicion-NN.md",
    "plan-changes/NN.md",
    "conformity.md",
)

# The reports of a plan folder the state script or a judgment role writes. An executor never
# edits one: when one fails a gate, the loop stops instead of the report being reworded.
CHAIN_REPORTS = ("gates/", "reviews/", "checks/", "plan-changes/", "conformity.md")

# The sections of an overview, in order. None of them holds the slices: the plan stays alive,
# and in the frozen contract any re-slicing would become a break.
OVERVIEW_SECTIONS = (
    "1. The idea in one sentence",
    "2. Acceptance criteria",
    "3. Scope and out of scope",
    "4. Data schema",
    "5. Architecture and boundaries",
    "6. Sequences",
    "7. State machines",
    "8. Algorithms",
    "9. Sensitive zones",
)

# The plan documents are written in the repository's language, not the conversation's.
# `/surface-plan` finds it once and writes it in `exploration.md`, where every agent and template
# names it, in these words; none of them follows the language of `specs.md` any more.
DOCUMENTS_LANGUAGE = "the language `exploration.md` names in its repository rules"
FORMER_LANGUAGE_RULE = "language of `specs.md`"
# Where `/surface-plan` finds that language, in this order, the first that answers winning: what
# the agent instructions declare, the repository's own documentation, then the specs.
LANGUAGE_SOURCES = (
    "A language the agent instructions (`AGENTS.md`, `CLAUDE.md`) declare",
    "Otherwise the language of the repository's own documentation",
    "Otherwise the language the specs are written in",
)
# The developer's own words stay as given and come with a translation; the agents read the
# translation and hold to the original when the two disagree.
WORK_FROM_TRANSLATION = "work from its translation: the original is the reference"
