# Evaluation of the chain

Chain `6bf7c06609a6`, measured on 2026-10-03T17:35:40Z: 6 runs over 6 cases. A value is the mean over the runs of a case, with its lowest and highest when they differ; a truth counts 1. An empty cell does not apply.

## Does it meet its goals

| | 01-overdue-list | 02-reservations | 03-overdue-reminders | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|---|---|
| `handed_over` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `conformant` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `acceptance` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `approved_by_sentence` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `questions` | 0 | 4 | 0 | 2 | 1 | 1 | 1.3333 (0 to 4) |
| `corrections` | 2 | 0 | 1 | 0 | 0 | 0 | 0.5 (0 to 2) |
| `planning_passes` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `reviews` | 1 | 2 | 1 | 1 | 1 | 1 | 1.1667 (1 to 2) |
| `fixes` | 0 | 1 | 0 | 0 | 0 | 0 | 0.1667 (0 to 1) |
| `zones_named` |  |  |  |  | 1 |  | 1 |
| `zones_none_said` | 1 | 1 | 1 | 1 |  | 1 | 1 |
| `zones_files_listed` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `zones_consistent` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `frame` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `body_sections` | 1 | 7 | 1 | 4 | 3 | 1 | 2.8333 (1 to 7) |
| `body_in_range` | 1 | 0 | 0 | 1 | 0 | 1 | 0.5 (0 to 1) |
| `diagrams` | 0 | 3 | 1 | 2 | 2 | 1 | 1.5 (0 to 3) |
| `diagram_as_expected` | 1 | 1 | 1 |  | 0 | 0 | 0.6 (0 to 1) |
| `cut_kept` | 1 | 1 | 1 |  |  |  | 1 |
| `plan_minimum` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `contaminated` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `usd` | 2.8559 | 4.4298 | 3.0198 | 1.9699 | 1.8687 | 1.5302 | 2.6124 (1.5302 to 4.4298) |

Outcomes: `01-overdue-list` conformant; `02-reservations` conformant; `03-overdue-reminders` conformant; `04-suspension` conformant; `05-fine-cap` conformant; `06-borrow-limit` conformant.

## Faults put there on purpose

| Probe | What | Found | Passed |
|---|---|---|---|
| `faithful-blueprint` | a blueprint that shows all the plan does | `0` | yes |
| `hidden-column` | the plan exports the ISBN as a fourth column, the blueprint says it is left out | `1` | yes |
| `hidden-effect` | the plan rewrites the developer's shelf file, the blueprint does not say so | `1` | yes |
| `hidden-zone` | the plan touches the critical zone of the toy, the blueprint says it touches none | `2` | yes |
| `seeded-break` | a commit of the developer adds a column the blueprint leaves out | `{"deviations": 0, "defects": 0, "breaks": 1}` | yes |
| `seeded-defect` | lines sorted by title only, which no test sees | `{"deviations": 0, "defects": 2, "breaks": 0}` | yes |
| `seeded-deviation` | the tests of slice 1 in another file than the plan names | `{"deviations": 1, "defects": 0, "breaks": 0}` | yes |
| `work-as-planned` | both slices done as the plan says | `{"deviations": 0, "defects": 0, "breaks": 0}` | yes |

## Is it good to work with

Scores from 1 to 5, by the judge.

| | 01-overdue-list | 02-reservations | 03-overdue-reminders | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|---|---|
| `blueprint.cut` | 3 | 3 | 3 | 3 | 4 | 3 | 3.1667 (3 to 4) |
| `blueprint.decidable` | 5 | 4 | 5 | 5 | 4 | 5 | 4.6667 (4 to 5) |
| `blueprint.diagrams` | 5 | 4 | 3 | 4 | 3 | 5 | 4 (3 to 5) |
| `blueprint.no-padding` | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| `following.no-noise` | 2 | 2 | 2 | 2 | 2 | 3 | 2.1667 (2 to 3) |
| `following.whose-turn` | 4 | 3 | 4 | 4 | 5 | 4 | 4 (3 to 5) |
| `following.why-stopped` | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| `grounded` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `interview.no-invented-rule` | 4 | 4 | 4 | 5 | 4 | 5 | 4.3333 (4 to 5) |
| `interview.not-already-answered` | 5 | 5 | 5 | 5 | 5 | 4 | 4.8333 (4 to 5) |
| `interview.questions-matter` | 4 | 5 | 3 | 5 | 5 | 5 | 4.5 (3 to 5) |
| `interview.right-number` | 3 | 4 | 2 | 5 | 4 | 5 | 3.8333 (2 to 5) |
| `messages.clear` | 2 | 2 | 2 | 3 | 2 | 3 | 2.3333 (2 to 3) |
| `messages.next-step` | 3 | 3 | 3 | 2 | 3 | 3 | 2.8333 (2 to 3) |
| `messages.right-length` | 3 | 3 | 3 | 3 | 3 | 3 | 3 |

The lowest score of each criterion, with the judge's reason and its passage:

- `blueprint.cut`, 3 in `01-overdue-list`: The body is a single section, 'The overdue command', that runs several separately decidable behaviors together: selection, order and ties, the source of today, argument refusal, and empty or missing-file output. None of them gets its own titled section. Passage: "## The overdue command"
- `blueprint.decidable`, 4 in `02-reservations`: Every interview answer, the amendment to 5 days, the refusal order, the output lines and the file shape are stated, so the developer has the rules to decide on. One detail points elsewhere: the fields of the `hold` notice are given only as the same as an existing kind that the page never shows. Passage: "The outbox gains the notice kind `hold`, with the same fields as `fine`."
- `blueprint.diagrams`, 3 in `03-overdue-reminders`: The sequence diagram mostly draws a linear call chain between internal modules, which is implementation detail. Its only branch, skip or remind, is a simple fork that the prose already states. Passage: "participant N as notices.py (existing, + load_notices, recently_reminded, REMINDER, REMINDER_DAYS)"
- `blueprint.no-padding`, 2 in `01-overdue-list`: The text tie rule is stated in criterion 3, again in the body, again in the 'Compared as text' paragraph, and once more under sensitive zones; the missing-file case is likewise repeated in the criteria, the body and two sensitive-zone bullets. Implementation details (argparse, counting 'once', `main` falling back to the clock) and draft history also appear, and none of these are the developer's to decide. Passage: "The order rests on one key with two parts: days late, highest first, then book id, in ascending text order. The lines therefore depend only on the loans themselves, never on their order in `loans.jsonl`, and nothing relies on the sort keepi [...]"
- `following.no-noise`, 2 in `01-overdue-list`: The missing `gh` and pull request appear at four stops, and the unchanged gate and the checker's clean result recur at each revision. Internal chain mechanics are also narrated for their own sake, such as the HTML-escaped return and the correction to `exploration.md`. Passage: "- **Pull request:** `gh` isn't installed, so there is still no draft PR. The description I gave you earlier is still accurate. - **Gate:** unchanged, `python3 -m unittest discover -s tests -q`."
- `following.whose-turn`, 3 in `02-reservations`: Stops 1–7 each end with a clear question or a clear call to launch `/surface-execute`. The final stop asks the developer to mark a pull request ready and says this triggers their CI, yet stop 5 said there is no pull request and no CI, so the last expected action is impossible as stated. Passage: "Nothing is left to check. Mark the pull request ready when you want, which triggers your CI. To update its description, run `surface-status pr-body` and paste the output in by hand."
- `following.why-stopped`, 5 in `01-overdue-list`: Every stop states its reason: a plan awaiting approval with the approving action named, a reply that does not count as approval with that reason given, and the work done and conformant. There is no lapse. Passage: "A reply here doesn't approve the plan, so I've recorded nothing. Only launching `/surface-execute` approves revision 3, and I can't launch it for you."
- `interview.no-invented-rule`, 4 in `01-overdue-list`: The final blueprint's rules all come from the need, the code, or the developer's amendments, and the ISO date is labeled as an assumption. One small lapse: the empty-output-with-exit-0 behavior was an assumption in the interview, but the blueprint states it as a plain criterion and never offers it to the developer to confirm. Passage: "5. When no loan is late, nothing is printed and the exit code is 0. The same holds when the data directory has no `loans.jsonl`."
- `interview.not-already-answered`, 4 in `06-borrow-limit`: The question itself was open: neither the need nor the code sets a limit. But the recommendation claims the specs and README make no distinction between members, while the README's Data section already declares the `student` and `staff` categories, so it steered toward a default the code argues against. Passage: "Recommended: A, the specs name no distinction between members and the README rules treat them alike; 5 is a common library default, but the number is the developer's to confirm."
- `interview.questions-matter`, 3 in `03-overdue-reminders`: The interview asked nothing. It labelled real business rules as "implementation matters": whether a member unknown to `members.jsonl` gets a reminder, which notice kinds count, and the order of members. Those were the developer's to decide, and the interview kept them away from the developer. Passage: "The remaining points are implementation matters, recorded as assumptions in the plan:"
- `interview.right-number`, 2 in `03-overdue-reminders`: With zero questions, the core business rule (how often a member may be reminded) was settled by a guess, and the developer had to amend it after reading the blueprint. The contract with the mailer was never asked about either: it receives a new `reminder` kind, and the guard only works if the outbox is never emptied. Passage: "> The blueprint gets the once-a-day rule wrong. A member must be reminded again only 7 days or more after their last reminder."
- `messages.clear`, 2 in `01-overdue-list`: Several messages rely on the chain's own vocabulary ("the checker", "slice", "gate", "the loop", "critical zones", "Amendment 2", the Plan agent's escaped return), which the developer cannot act on. Stop 5 also assumes a pull request exists, contradicting the earlier statements that none was opened. Passage: "- **One deviation:** the `Plan` agent's return reached me with `<` and `>` HTML-escaped. I wrote `plan.md` with the real characters, because the `<!-- slice:1 -->` marker has to be literal. Otherwise it is as returned."
- `messages.next-step`, 2 in `04-suspension`: Stop 5 tells the developer to mark the pull request ready, but no pull request was ever opened because `gh` was missing; the right step is to open it first. Stop 4 also ends on a status remark instead of the action, and Stop 1 ends on what the agent will ask later. Passage: "**Your turn:** mark the pull request ready when you want, which triggers your CI."
- `messages.right-length`, 3 in `01-overdue-list`: Stops 2 and 3 restate test names, file edits and Risks wording that belong to the plan the developer is sent to read, and Stop 1 spends a bullet on an internal escaping glitch. Stop 5 leaves out what the developer needs: there is still no pull request, and the pasted description should now say conformant. Passage: "- **Pull request description:** it is not refreshed. `gh` isn't installed here, so `surface-status pr-body` couldn't be sent to the pull request."

## The judge, checked

| Spoiled document | Criterion | Original | Spoiled | Below |
|---|---|---|---|---|
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `blueprint.no-padding` | [3, 3] | [2, 2] | yes |
| a blueprint stripped of the two rules the interview settled, and of the ISBN left out | `blueprint.decidable` | [3, 4] | [2, 2] | yes |
| an interview with two questions the need and the code already answer | `interview.not-already-answered` | [5, 5] | [2, 2] | yes |

## Cost

101 sessions, 18.71 USD at list price. The weekly gauge of the subscription rose by 3 points while they ran, every other use of the account included.
