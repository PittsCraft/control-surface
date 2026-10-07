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
# On conformant, the loop hands back in one line, and that line is all the session says: the plan
# is conformant, the changed files of the critical zones when there are any, then the developer's
# step, last. No report of what was done: the description of the pull request holds it, and a
# report in the terminal buried the step. A criterion the reviewer cannot prove is a finding, so a
# conformant plan leaves nothing to check: `conformity.md` is kept, never a required reading. The
# chain never marks the pull request ready, since that triggers the host's CI.
CONFORMANT_HAND_BACK = "hand back in one line, which is all you say at this stop"
CONFORMANT_STEP = "the developer marks the pull request ready when they want"
# A branch may have no pull request: no `gh`, no remote, or a push the developer declined. The
# line then names the step that fits, since nobody marks ready a pull request that does not exist.
CONFORMANT_WITHOUT_PULL_REQUEST = (
    "the developer opens the pull request, if none is open yet, with the description"
    " `surface-status pr-body` prints"
)
# The one exception, which the line names: where a mistake would cost most, in the zones the
# host's agent instructions declare critical, the developer reads the code themselves. The line
# names the files the branch changed there, the list the pull request description gives, which
# the session reads in the answer of `pr-body`.
CONFORMANT_EXCEPTION = (
    "a conformant plan leaves nothing to check, except the code of the critical zones"
)
# So the developer learns at approval which zones those will be: the closing section of the
# blueprint, the sensitive zones, names each declared critical zone the plan touches, or says the
# plan touches none, and the cross-check counts a touched zone it does not name as an omission.
CRITICAL_ZONES_OF_THE_PLAN = (
    "each critical zone the repository's agent instructions declare that the plan touches"
)
TOUCHES_NONE = "the plan touches none"
UNNAMED_ZONE = "A critical zone the plan touches and the sensitive zones do not name is an omission"
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

# A blueprint has a fixed frame and a free body. It opens with these sections, in this order, and
# closes with the last one, so what the work is judged against is always found in the same place.
# None of them holds the slices: the plan stays alive, and in the frozen contract any re-slicing
# would become a break. No heading carries a number: a section is cited by its title, which an
# amendment does not move.
BLUEPRINT_OPENING = (
    "The idea in one sentence",
    "Acceptance criteria",
    "Scope and out of scope",
)
BLUEPRINT_CLOSING = "Sensitive zones"
# Between them the extractor cuts the body by what the developer decides separately, and keeps
# the cut of the previous revision. Inside a section, a title in bold opens each thing the
# developer would come back for on its own. Whatever the cut, it goes through these aspects, and
# one closing line names those the plan leaves alone, since silence must not read as "unchanged".
# A diagram is drawn where what it shows has a shape that prose flattens. The cross-check never
# counts a cut, a short section or the absence of a diagram as an omission, only what the
# blueprint does not show.
BLUEPRINT_ASPECTS = (
    "the data schema",
    "the architecture and its boundaries",
    "the sequences",
    "the state machines",
    "the algorithms",
)
CLOSING_LINE = "No change:"

# The plan is drafted by the `Plan` agent built into Claude Code, which the chain neither installs
# nor defines, in the form that agent chooses. It is held to the minimum the chain reads, the
# headings of its template: the acceptance criteria, numbered, which the blueprint carries and the
# review cites; the slices, each behind the marker the state script reads; the `gates` block the
# script runs. No heading carries a number, so no prompt names a section of the plan by one.
PLAN_AGENT = "Plan"
PLAN_MINIMUM = ("Acceptance criteria", "Slices", "Gates")
# That agent cannot ask the developer anything. A rule a user of the feature would see applied,
# which neither the specs, an answer of the developer nor the code settles, it settles on its
# own and marks wherever the plan states it. The extractor shows it on the blueprint as an
# assumption, never as settled, in words that stay true once the page is frozen: approving
# confirms it, and planning gains no step. The line is the one the interview draws, in its
# words: a matter of implementation is no such assumption.
ASSUMPTION_OF_THE_PLAN = "an assumption of the plan, which approving the blueprint confirms"
THE_DEVELOPERS_RULES = (
    "a rule that a user of the feature, or a program that reads what it writes, would see"
    " applied: an order, ties included, a number, a frequency or a limit, who or what is"
    " counted or left out, what is refused"
)

# How a commit of the work is written or signed is known to the agent that writes it, which
# follows the conventions of the host. That agent is not the one that drafts the plan, and the
# blueprint is frozen before the commit exists: a line of either on it promises what another agent
# decides, and in the blueprint a commit written another way is a contract break. So neither says
# anything of its own on it. A slice carries what the conventions or the developer ask, since an
# executor reads the plan and never the interview, and the blueprint only what the developer asked.
COMMIT_FORM = "written or signed"
SLICE_ON_ITS_COMMIT = "beyond what the conventions of the repository or the developer ask"
BLUEPRINT_ON_THE_COMMITS = "beyond what the developer asked"
# The prompts stop there. The attribution Claude Code adds to a commit is left to the settings of
# the host, and the guide names the one that turns it off: no prompt asks for one or forbids one.
ATTRIBUTION_WORDS = ("attribution", "co-authored")

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
# What a command tells the developer is said in the words the README and the guide teach them,
# listed here as the rubric of the judge lists them. The names of the other agents and the
# paths of the reports are the chain's insides, and stay out of a message: it is to be acted
# on, not to narrate the chain. A report is named when the developer has to open it or asks for
# it, and a plan change proposal is no report: it is theirs to decide on.
TAUGHT_WORDS = (
    "the plan and the blueprint, its cut, a revision, an amendment, the gates, the critical"
    " zones, a slice, a review and its reviewer, a defect, a pass and the ceiling, the loop, the"
    " cross-check, a contract break and its plan change proposal, conformant"
)
INSIDES = "The chain's insides stay out of what you say: the name of any agent but the reviewer"
# The developer's own words stay as given and come with a translation; the agents read the
# translation and hold to the original when the two disagree.
WORK_FROM_TRANSLATION = "work from its translation: the original is the reference"
