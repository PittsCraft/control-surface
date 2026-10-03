# Evaluation of the chain

Chain `e830bc236e9b`, measured on 2026-10-03T21:09:36Z: 6 runs over 2 cases. A value is the mean over the runs of a case, with its lowest and highest when they differ; a truth counts 1. An empty cell does not apply.

## Does it meet its goals

| | 01-overdue-list | 03-overdue-reminders | all |
|---|---|---|---|
| `handed_over` | 1 | 1 | 1 |
| `conformant` | 1 | 1 | 1 |
| `acceptance` | 1 | 1 | 1 |
| `approved_by_sentence` | 0 | 0 | 0 |
| `questions` | 1 | 0.3333 (0 to 1) | 0.6667 (0 to 1) |
| `corrections` | 1 (0 to 2) | 1 | 1 (0 to 2) |
| `planning_passes` | 0 | 0 | 0 |
| `reviews` | 1 | 1 | 1 |
| `fixes` | 0 | 0 | 0 |
| `zones_none_said` | 1 | 1 | 1 |
| `zones_files_listed` | 1 | 1 | 1 |
| `zones_consistent` | 1 | 1 | 1 |
| `frame` | 1 | 1 | 1 |
| `body_sections` | 1.3333 (1 to 2) | 1.6667 (1 to 3) | 1.5 (1 to 3) |
| `body_in_range` | 0.6667 (0 to 1) | 0.3333 (0 to 1) | 0.5 (0 to 1) |
| `diagrams` | 0.3333 (0 to 1) | 1.6667 (1 to 3) | 1 (0 to 3) |
| `diagram_as_expected` | 0.6667 (0 to 1) | 1 | 0.8333 (0 to 1) |
| `cut_kept` | 0.5 (0 to 1) | 1 | 0.8 (0 to 1) |
| `plan_minimum` | 1 | 1 | 1 |
| `contaminated` | 0 | 0 | 0 |
| `usd` | 2.3444 (1.4078 to 3.6023) | 2.8408 (2.6525 to 3.1135) | 2.5926 (1.4078 to 3.6023) |

Outcomes: `01-overdue-list` conformant, conformant, conformant; `03-overdue-reminders` conformant, conformant, conformant.

## Is it good to work with

Scores from 1 to 5, by the judge.

| | 01-overdue-list | 03-overdue-reminders | all |
|---|---|---|---|
| `blueprint.cut` | 3.6667 (3 to 4) | 4 | 3.8333 (3 to 4) |
| `blueprint.decidable` | 4.3333 (4 to 5) | 4.6667 (4 to 5) | 4.5 (4 to 5) |
| `blueprint.diagrams` | 4.6667 (4 to 5) | 3.6667 (3 to 4) | 4.1667 (3 to 5) |
| `blueprint.no-padding` | 2 | 2 | 2 |
| `following.no-noise` | 2 | 2 | 2 |
| `following.whose-turn` | 4 | 4.3333 (4 to 5) | 4.1667 (4 to 5) |
| `following.why-stopped` | 5 | 5 | 5 |
| `grounded` | 1 | 1 | 1 |
| `interview.no-invented-rule` | 4 (3 to 5) | 3 (2 to 4) | 3.5 (2 to 5) |
| `interview.not-already-answered` | 5 | 4.6667 (4 to 5) | 4.8333 (4 to 5) |
| `interview.questions-matter` | 5 | 3 | 4 (3 to 5) |
| `interview.right-number` | 3.3333 (2 to 5) | 2 | 2.6667 (2 to 5) |
| `messages.clear` | 2 | 3 | 2.5 (2 to 3) |
| `messages.next-step` | 3.3333 (3 to 4) | 4 | 3.6667 (3 to 4) |
| `messages.right-length` | 3.3333 (3 to 4) | 3.6667 (3 to 4) | 3.5 (3 to 4) |

The lowest score of each criterion, with the judge's reason and its passage:

- `blueprint.cut`, 3 in `01-overdue-list`: The body follows a generic template, and its one feature section, "The overdue list", restates the acceptance criteria. That section also mixes the visible ordering rule with an architecture choice, so the cut is not by what the developer decides. Passage: "## The overdue list"
- `blueprint.decidable`, 4 in `01-overdue-list`: Every interview answer is carried: the text tie-break, always exit 0, and empty or missing file. The one gap is that the days-late figure is defined only as whatever `fines.days_late` returns, so the developer must open `fines.py` to know the number printed for a loan due yesterday. Passage: "The number of days late on each line is the one the fine computation already uses (`fines.days_late`). Nothing new is computed about lateness."
- `blueprint.diagrams`, 3 in `03-overdue-reminders`: The interval flowchart earns its place because the path branches. The sequence diagram is mostly a linear chain of internal reads and calls with one loop, and prose already states that order, so the diagram shows module plumbing rather than a shape the developer needs. Passage: "R->>L: load_loans L->>S: read loans.jsonl R->>N: load_notices (new) N->>S: read outbox.jsonl"
- `blueprint.no-padding`, 2 in `01-overdue-list`: Several facts are said more than once: `B10` before `B2` appears three times, the missing-file case is in criterion 5 and again in the body, and the member-id assumption is in the body and again in sensitive zones. A paragraph is also spent on which module holds the sort, an implementation detail that is not the developer's to decide. Passage: "By approving this, you accept that the sort lives in the command itself, in `lending/__main__.py`, not in the domain."
- `following.no-noise`, 2 in `01-overdue-list`: Several facts recur across stops: the rule that only `/surface-execute` approves appears at stops 2, 3 and 4, the unchanged gate command at stops 2, 3 and 5, and the missing `gh` at stops 2 and 5. Steps of the chain are also narrated for their own sake, such as the redrawn blueprint, the cross-check, and the reviewer writing `conformity.md`. Passage: "The blueprint was redrawn and the cross-check found no omissions."
- `following.whose-turn`, 4 in `01-overdue-list`: Every stop makes the developer's turn and expected action clear: answer Q1, amend or launch `/surface-execute`, or say whether the exit-2 reading is wrong. The one lapse is at the last stop, which says nothing is left for the developer yet tells them to mark a pull request ready to trigger 'your CI', when no pull request exists and an earlier stop said no CI is configured. Passage: "Mark it ready when you want, which triggers your CI."
- `following.why-stopped`, 5 in `01-overdue-list`: Each stop names its reason: an open question, a drafted plan handed over for approval, an amended plan with one decision for the developer, a refusal to treat 'Looks fine' as approval, and finished work. No stop ends without saying why. Passage: "\"Looks fine\" doesn't approve the plan. Only launching `/surface-execute` does, so I'm recording nothing and starting no work."
- `interview.no-invented-rule`, 2 in `03-overdue-reminders`: Several visible rules were decided without the developer and stated as settled, not as assumptions to confirm: the exact text of the notice members receive, skipping members whose reminder is dated after today, and reminding loans whose member is unknown. None comes from the need, an answer or the code. Passage: "The wording of the notice is fixed by the plan, since the specs leave it open: `Overdue books: B1, B3. Fine owed as of 2026-03-20: 1.75.`"
- `interview.not-already-answered`, 4 in `03-overdue-reminders`: The code largely settles the order already: `load_loans` and `overdue` return loans in file order, and the README says `loans` prints "in the order of the file". The question even cites that precedent in its recommendation. Only grouping by member was left open. Passage: "Recommended: A, it matches the precedent of `loans` (\"in the order of the file\") and needs no sort rule."
- `interview.questions-matter`, 3 in `03-overdue-reminders`: No question was asked, so no question was wasted. But the only questions that would have changed the build, such as the reminder frequency and whether the mailer accepts a new notice kind, were never put to the developer. Passage: "None. The specs and the code settle every rule a user of the command, or the mailer, would see applied:"
- `interview.right-number`, 2 in `01-overdue-list`: The interview asked only about tie order. It asked nothing about extra arguments or about a missing or empty `loans.jsonl`. The plan guessed both, including an exit code of 2 for `overdue M1`, and the developer had to correct them in two amendments. Passage: "Don't make an extra argument such as `overdue M1` exit with code 2; criterion 6 and the edge-case paragraph say otherwise."
- `messages.clear`, 2 in `01-overdue-list`: Several messages use the chain's internal vocabulary that the developer was never given, such as "no cut", "Gate the loop will run", "cross-check found no omissions", "Slice 1", "critical-zone files", and "defects, deviations and breaks". The final message is the heaviest offender: it reports the result almost entirely in pipeline terms. Passage: "**Review:** the reviewer found 0 defects, 0 deviations and 0 breaks (`reviews/pass-01.md`). It wrote `conformity.md`, and it lists no critical-zone files because the branch changed neither `lending/fines.py` nor `lending/loans.py`."
- `messages.next-step`, 3 in `01-overdue-list`: Stop 1 ends on what the agent will do rather than on the developer answering Q1. Stop 5 ends on a status line, after a muddled step: running `pr-body` only prints text, and "mark it ready" refers to a pull request nobody has opened, since `gh` is missing. Passage: "To open the pull request, run `.claude/skills/surface-status/scripts/surface-status pr-body`, which prints the description. Mark it ready when you want, which triggers your CI."
- `messages.right-length`, 3 in `01-overdue-list`: Stop 4 leaves out something the developer needs: it sends them to run an internal script for the pull request description instead of giving the text, as Stop 2 did. Stop 2 also spends lines on internals the developer won't act on, such as the circular-import placement and the blueprint cut. Passage: "If no pull request is open yet, open one with the description from `.claude/skills/surface-status/scripts/surface-status pr-body`."

## Cost

67 sessions, 17.07 USD at list price. The weekly gauge of the subscription rose by 5 points while they ran, every other use of the account included.

## What moved since the campaign before

- `01-overdue-list` `questions`: 0 then 1, moved.
- `01-overdue-list` `interview.questions-matter`: 4 then 5, better.
- `03-overdue-reminders` `criteria`: 13 then 10 (9 to 12), moved.
- `03-overdue-reminders` `words`: 1444 then 1309.67 (1235 to 1425), moved.
- `03-overdue-reminders` `blueprint.cut`: 3 then 4, better.
- `03-overdue-reminders` `messages.clear`: 2 then 3, better.
- `03-overdue-reminders` `messages.next-step`: 3 then 4, better.
