"""The contract of the chain that the prompts must carry, stated once for the prompt tests.

The state script holds its own contract in code. The prompts hold theirs in prose, so the tests
state here what the chain promises a developer, and check that each prompt says it: how a review
classifies a finding, which command acts on a plan in each state, in which order planning records
its events and the execution loop reads its rows, what the reviewer writes, and the sections of an
overview.
"""

# A review classifies a finding by two closed questions, in this order. A yes to the first is a
# contract break; otherwise a yes to the second is a defect, the code is fixed, and a no a
# deviation, the plan is amended.
BREAK_QUESTION = "Must the overview be modified for it to stay true?"
DEFECT_QUESTION = "Must the code be fixed?"
# A review with no finding ends the loop in this state.
NO_FINDING_END = "conform state"

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
