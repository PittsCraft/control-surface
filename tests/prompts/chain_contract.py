"""The contract of the chain that the prompts must carry, stated once for the prompt tests.

The state script holds its own contract in code. The prompts hold theirs in prose, so the tests
state here what the chain promises a developer, and check that each prompt says it: how a review
classifies a finding, which command acts on a plan in each state, which acts of the developer each
command takes in the conversation, in which order planning records its events and the execution
loop reads its rows, what the reviewer writes, the sections of a blueprint and its length, the
critical zones whose code the developer still reads, and the language of the plan documents.
"""

# A review classifies a finding by two closed questions, in this order. A yes to the first is a
# contract break; otherwise a yes to the second is a defect, the code is fixed, and a no a
# deviation, the plan is amended.
BREAK_QUESTION = "Must the blueprint be modified for it to stay true?"
DEFECT_QUESTION = "Must the code be fixed?"
# A review with no finding ends the loop in this state.
NO_FINDING_END = "conformant state"
# On conformant, the loop hands back in one line. A criterion the reviewer cannot prove is a
# finding, so a conformant plan leaves nothing to check: `conformity.md` is kept, never a required
# reading. The chain never marks the pull request ready, since that triggers the host's CI.
CONFORMANT_HAND_BACK = (
    "the plan is conformant, and the developer marks the pull request ready when they want"
)
# The one exception, which the hand-back says in one sentence: where a mistake would cost most,
# in the zones the host's agent instructions declare critical, the developer reads the code
# themselves, from the list of changed files the pull request description gives.
CONFORMANT_EXCEPTION = (
    "a conformant plan leaves nothing to check, except the code of the critical zones"
)
# So the developer learns at approval which zones those will be: section 9 of the blueprint names
# each declared critical zone the plan touches, or says the plan touches none, and the cross-check
# counts a touched zone that section 9 does not name as an omission.
CRITICAL_ZONES_OF_THE_PLAN = (
    "each critical zone the repository's agent instructions declare that the plan touches"
)
TOUCHES_NONE = "the plan touches none"
UNNAMED_ZONE = "A critical zone the plan touches and section 9 does not name is an omission"
# At conformity the reviewer lists the files the branch changed inside those zones, in a fenced
# block of `conformity.md` that the state script alone takes up, in the pull request description.
CRITICAL_FILES_OF_THE_BRANCH = (
    "the files the branch changed inside the critical zones the repository's agent instructions"
    " declare"
)
# A list the script refuses is an agent's mechanical mistake, never the developer's to repair:
# they are told not to open `conformity.md`. `/surface-execute` sends it to a fresh reviewer,
# the third thing a reviewer is launched for, whose only mandate is to correct that block, then
# records `conformant` again, as many times as the ceiling of autonomous passes, the one setting
# that bounds what the loop does on its own; still refused after them, it hands back to the
# developer. The count is the prompt's, since a refused `conformant` leaves no journal line: no
# pass counted, no journal event, no new gate run, no new review.
REVIEWER_MODES = (
    "a review",
    "a break an executor suspected during slice N, with its reason",
    "a refused list of critical files, with the refusal's reason",
)
REFUSED_LIST = "a refused list of critical files"
CORRECTIONS_CEILING = "up to `passes.ceiling` of `show --json` reviewers in all"

# The commands that act on a plan in each state where work remains. The other command does not
# see the plan: it neither resumes it nor offers it, and `resolve` does not find it for it.
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
    "`conformant`, `abandoned`",
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

# The sections of a blueprint, in order. None of them holds the slices: the plan stays alive,
# and in the frozen contract any re-slicing would become a break.
BLUEPRINT_SECTIONS = (
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
# A blueprint is as long as the feature needs: the developer reads all of it. These sections are
# always written; one of the others is written only when the plan changes what it shows, under
# its own number, and one closing line names those left out. A diagram is drawn only when it
# shows what the prose does not. The cross-check never counts a short section or the absence of
# a diagram as an omission, only what the blueprint does not show.
ALWAYS_WRITTEN = (
    "1. The idea in one sentence",
    "2. Acceptance criteria",
    "3. Scope and out of scope",
    "9. Sensitive zones",
)
CLOSING_LINE = "No change:"

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
