# Evaluation of the chain

Chain `9d5de55f57a9`, measured on 2026-10-07T13:33:17Z: 12 runs over 6 cases. A value is the mean over the runs of a case, with its lowest and highest when they differ; a truth counts 1. An empty cell does not apply.

4 of these runs played planning alone, on purpose: they went no further than the hand over, and nothing was approved or built in them. No measure of the execution counts them, here or against another campaign, and what the judge says of their stops is kept apart, under the dimensions that end in `-in-planning`.

## Does it meet its goals

| | 01-overdue-list | 02-reservations | 03-overdue-reminders | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|---|---|
| `handed_over` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `conformant` |  | 1 |  | 1 | 1 | 1 | 1 |
| `acceptance` |  | 1 |  | 1 | 1 | 1 | 1 |
| `approved_by_sentence` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `questions` | 1 | 6 | 2 | 4 | 1 | 3 | 2.8333 (1 to 6) |
| `questions_handed_back` | 0 | 1 | 2 | 0.5 (0 to 1) | 0 | 1 | 0.75 (0 to 2) |
| `corrections` | 1 | 0 | 0 | 0 | 0 | 0.5 (0 to 1) | 0.25 (0 to 1) |
| `expected_correction` |  |  | 1 |  |  |  | 1 |
| `planning_passes` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `reviews` |  | 1 |  | 1 | 1.5 (1 to 2) | 1 | 1.125 (1 to 2) |
| `fixes` |  | 0 |  | 0 | 0.5 (0 to 1) | 0 | 0.125 (0 to 1) |
| `pr_draft_at_hand_over` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `pr_described` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `pr_refreshed` |  | 1 |  | 1 | 1 | 1 | 1 |
| `pr_marked_ready` |  | 0 |  | 0 | 0 | 0 | 0 |
| `gh_not_played` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `zones_named` |  |  |  |  | 1 |  | 1 |
| `zones_none_said` | 1 | 1 | 1 | 0 |  | 1 | 0.8 (0 to 1) |
| `zones_files_listed` |  | 1 |  | 1 | 1 | 1 | 1 |
| `zones_announced` |  | 0.5 (0 to 1) |  | 1 | 1 | 0 | 0.625 (0 to 1) |
| `frame` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `body_sections` | 1 | 4 (3 to 5) | 3 | 2.5 (2 to 3) | 1 | 1 | 2.0833 (1 to 5) |
| `body_in_range` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `inner_titles` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `untitled_long_sections` | 0.5 (0 to 1) | 2.5 (2 to 3) | 2 | 1.5 (1 to 2) | 1 | 0 | 1.25 (0 to 3) |
| `diagrams` | 0 | 2.5 (2 to 3) | 1 | 1 | 0 | 1 | 0.9167 (0 to 3) |
| `diagram_as_expected` | 1 | 1 | 1 |  | 1 | 0 | 0.8 (0 to 1) |
| `cut_kept` | 1 | 1 | 0.5 (0 to 1) |  |  | 1 | 0.8571 (0 to 1) |
| `plan_minimum` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `contaminated` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `planning_usd` | 1.4227 (1.3733 to 1.4721) | 2.5103 (2.4207 to 2.6) | 2.1231 (2.1169 to 2.1294) | 1.1813 (1.1017 to 1.261) | 0.9938 (0.9823 to 1.0053) | 1.3595 (0.9839 to 1.735) | 1.5985 (0.9823 to 2.6) |
| `usd` |  | 3.6243 (3.5023 to 3.7463) |  | 1.9146 (1.851 to 1.9783) | 1.863 (1.6719 to 2.0542) | 1.9726 (1.5938 to 2.3514) | 2.3436 (1.5938 to 3.7463) |

Outcomes: `01-overdue-list` stopped-at-hand-over, stopped-at-hand-over; `02-reservations` conformant, conformant; `03-overdue-reminders` stopped-at-hand-over, stopped-at-hand-over; `04-suspension` conformant, conformant; `05-fine-cap` conformant, conformant; `06-borrow-limit` conformant, conformant.

`03-overdue-reminders` expects one correction, which `expected_correction` tells and `corrections` leaves out. Its need states a rule the developer did not mean, on purpose: no member reminded twice on the same day, where they mean 7 days or more between two reminders of a member. A session that takes the need at its word plans the first, and what the case evaluates is that the error is caught when the developer reads the blueprint.

## Is it good to work with

Scores from 1 to 5, by the judge.

| | 01-overdue-list | 02-reservations | 03-overdue-reminders | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|---|---|
| `blueprint.cut` | 4.5 (4 to 5) | 4 | 3.5 (3 to 4) | 3.5 (3 to 4) | 4 | 3.5 (3 to 4) | 3.8333 (3 to 5) |
| `blueprint.decidable` | 4.5 (4 to 5) | 4 | 4.5 (4 to 5) | 4.5 (4 to 5) | 5 | 4.5 (4 to 5) | 4.5 (4 to 5) |
| `blueprint.diagrams` | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| `blueprint.no-padding` | 2 | 2 | 2 | 3 | 2 | 2 | 2.1667 (2 to 3) |
| `following-in-planning.no-noise` | 2 |  | 3 |  |  |  | 2.5 (2 to 3) |
| `following-in-planning.whose-turn` | 5 |  | 5 |  |  |  | 5 |
| `following-in-planning.why-stopped` | 5 |  | 5 |  |  |  | 5 |
| `following.no-noise` |  | 2.5 (2 to 3) |  | 2.5 (2 to 3) | 2.5 (2 to 3) | 3 | 2.625 (2 to 3) |
| `following.whose-turn` |  | 4.5 (4 to 5) |  | 5 | 4.5 (4 to 5) | 5 | 4.75 (4 to 5) |
| `following.why-stopped` |  | 4.5 (4 to 5) |  | 4.5 (4 to 5) | 4.5 (4 to 5) | 4 | 4.375 (4 to 5) |
| `grounded` | 1 | 1 | 1 | 1 | 0.9643 (0.9286 to 1) | 1 | 0.994 (0.9286 to 1) |
| `interview.no-invented-rule` | 4.5 (4 to 5) | 4.5 (4 to 5) | 4.5 (4 to 5) | 4 | 5 | 4 | 4.4167 (4 to 5) |
| `interview.not-already-answered` | 5 | 5 | 3 | 5 | 5 | 5 | 4.6667 (3 to 5) |
| `interview.questions-matter` | 5 | 3.5 (3 to 4) | 2 | 5 | 5 | 2.5 (2 to 3) | 3.8333 (2 to 5) |
| `interview.right-number` | 4 | 4 | 2.5 (2 to 3) | 4 | 4.5 (4 to 5) | 3.5 (3 to 4) | 3.75 (2 to 5) |
| `messages-in-planning.clear` | 3.5 (3 to 4) |  | 4 |  |  |  | 3.75 (3 to 4) |
| `messages-in-planning.next-step` | 4.5 (4 to 5) |  | 5 |  |  |  | 4.75 (4 to 5) |
| `messages-in-planning.right-length` | 4.5 (4 to 5) |  | 4 |  |  |  | 4.25 (4 to 5) |
| `messages.clear` |  | 4.5 (4 to 5) |  | 5 | 3.5 (3 to 4) | 4.5 (4 to 5) | 4.375 (3 to 5) |
| `messages.next-step` |  | 5 |  | 3.5 (3 to 4) | 4 | 5 | 4.375 (3 to 5) |
| `messages.right-length` |  | 3 |  | 3.5 (3 to 4) | 3 (2 to 4) | 4 | 3.375 (2 to 4) |

The lowest score of each criterion, with the judge's reason and its passage:

- `blueprint.cut`, 3 in `03-overdue-reminders`: The reminder-interval rule, one behavior the developer decides on its own, is split between criterion 6 and a separate outbox section that adds the past-date case and the partial-run behavior. The developer has to join the two to see the whole rule. Passage: "A member's last reminder is the latest date among the `reminder` notices addressed to them, not the last such line of the file."
- `blueprint.decidable`, 4 in `01-overdue-list`: The rules, output format, tie-break with its worked example, wrong usage deferred to the parser, and the empty-list assumption are all stated, with the interview answers carried. One detail is left to another file: days late are defined only as whatever `lending/fines.py` counts, anchored by the single 'yesterday is 1' case. Passage: "Days late are the ones the fine computation counts, with today taken from `--today` or from the real date."
- `blueprint.diagrams`, 5 in `01-overdue-list`: There is no diagram, and nothing here has a shape that needs one. The single relation between the command line, the loans module and the fine computation is a short dependency that a sentence states well. Passage: "The order is computed there, not in the loans module, because the days late come from the fine computation, and the fine computation already depends on the loans module: the loans module cannot call it back."
- `blueprint.no-padding`, 2 in `01-overdue-list`: Several facts are said twice. Scope repeats criterion 9 (no change to the fine computation) and criterion 7 (no own handling of wrong usage), and the critical-zones line restates criterion 9 instead of standing as a bare line. Passage: "Critical zones touched: none. The command reads `loans.jsonl` and relies on the day count of the fine computation (`lending/fines.py`) without changing either (criterion 9)."
- `following-in-planning.no-noise`, 2 in `01-overdue-list`: Several stops narrate chain steps for their own sake: creating the branch and folder, writing the exploration, cross-checking 'with nothing omitted', pushing, refreshing the pull request description, and explaining the cut. Stop 3 also ends on reassurance the developer did not need. Passage: "The changes are in the plan and blueprint only. No code has been written."
- `following-in-planning.whose-turn`, 5 in `01-overdue-list`: Every stop ends by putting the next move with the developer and saying what it is: answer Q1 with a recommendation, amend or approve by launching `/surface-execute`, or amend further. There is no stop where the developer is left unsure whether to act. Passage: "Do you want to amend further, or approve? To approve, launch `/surface-execute`; a reply here won't approve it."
- `following-in-planning.why-stopped`, 5 in `01-overdue-list`: Each stop names its reason: an open question (Q1), the blueprint handed over for approval, a revision handed back with what changed and why criterion 6 was kept, and a reply that does not approve. No stop leaves its cause implicit. Passage: "Saying \"go ahead\" here doesn't approve the plan. Only launching `/surface-execute` does, so I've recorded nothing and the plan is still awaiting approval."
- `following.no-noise`, 2 in `02-reservations`: Stops 7 and 8 narrate chain steps for their own sake (drawn, cross-checked, no omissions, pushed, PR description refreshed). Stop 8 then repeats the link, the unchanged cut and gate, and the outstanding assumptions already given at stop 7. Passage: "I redrew and cross-checked the blueprint, which found no omissions, then committed and pushed. The pull request description is refreshed."
- `following.whose-turn`, 4 in `02-reservations`: Every stop ends with a clear question or a named next step for the developer. One lapse of detail: stop 7 asks the developer to confirm eight rules but names only three, so what exactly is expected stays partly vague. Passage: "the plan settled eight small rules you didn't decide. Approving the blueprint confirms them, so check these in particular:"
- `following.why-stopped`, 4 in `02-reservations`: The interview, hand over and hand back stops each say why the session stopped. The final stop gives only the jargon state 'conformant' and does not say that the slices were built and reviewed against the blueprint. Passage: "The plan is conformant, and the branch changed no files in the critical zones."
- `interview.no-invented-rule`, 4 in `01-overdue-list`: Revision 1 set a rule the developer never chose: an extra argument exits with code 2. The developer had to strike it through an amendment. Every rule in the final blueprint comes from the need, the answer or the code. Passage: "Criterion 6 contradicts what I know: I don't decide what happens on wrong usage, so the command should do whatever the other commands do with an extra argument. Please drop the \"exits with code 2\" requirement and don't pin that behavior."
- `interview.not-already-answered`, 3 in `03-overdue-reminders`: The code already settles Q1: the README says `loans` prints in the order of the file, and the question names that convention as its own recommendation. Q2 is not settled by the code, because the existing `fine` notice fixes no wording for a reminder. Passage: "Recommended: A, it is the order the README gives for `loans`, so the output follows the file."
- `interview.questions-matter`, 2 in `03-overdue-reminders`: The developer answered both questions with "That's your call", so neither one asked for a business rule, a contract or a decision only they could make. The question that did matter was whether the mailer keeps the lines it has sent in the outbox, and it was never asked. Passage: "Answer (2026-10-07): \"That's your call; I don't rely on the order. Go with your recommendation, A.\""
- `interview.right-number`, 2 in `03-overdue-reminders`: The interview never asked what "No member is reminded twice on the same day" should mean in practice. The plan guessed it, and the developer had to correct it with an amendment that set the 7-day interval. The two questions it did ask were there for thoroughness, and whether the total should include fines from returned loans was left as an assumption rather than asked. Passage: "1. Criterion 6 is wrong. A member is reminded again only 7 days or more after their last reminder, so a reminder dated the 1st blocks them through the 7th and they are reminded again from the 8th."
- `messages-in-planning.clear`, 3 in `01-overdue-list`: Stop 3 names the executor, an internal agent, in a message to the developer. The other messages keep to the chain's own words and match the plan state. Passage: "The plan also warns the executor not to add a test or README sentence about it."
- `messages-in-planning.next-step`, 4 in `01-overdue-list`: Stops 2 and 3 end on the right choice, to amend or to launch `/surface-execute`, and Stop 4 repeats that only the launch approves. Stop 1 ends on its recommendation without plainly asking the developer to reply with A, B or C. Passage: "I'd pick **A**. It matches `loans`, it adds no new rule, and the desk sees the same relative order in both lists."
- `messages-in-planning.right-length`, 4 in `01-overdue-list`: Most messages are as long as they need to be, and Stop 3 rightly spends words on why `B10` comes before `B2`. Its second point, though, describes the new test in detail and then admits the blueprint says the same, repeating a file the developer is sent to read. Passage: "The new test calls `overdue B1` and the existing wrong-usage case, then checks that both exit codes are equal and that standard output is empty. It doesn't write a literal code. The blueprint says the same."
- `messages.clear`, 3 in `05-fine-cap`: The last message says marking the pull request ready triggers the developer's CI. The earlier message said the repository has no CI, so the developer is told two contradictory things about what their next action sets off. Passage: "When you want, mark pull request #1 ready, which triggers your CI."
- `messages.next-step`, 3 in `04-suspension`: Stop 1 ends on a preview of later questions and what the agent will do, not on the answer the developer owes to Q1. Stop 4 likewise closes on an assumption taken as settled rather than on the question to answer. Passage: "I'll ask these one at a time."
- `messages.right-length`, 2 in `05-fine-cap`: Stop 4 gives only the state and says nothing of what was built: no slices, no gate results, no review outcome or defects fixed. Stop 2 never says whether the blueprint covers the developer's added rule for a loan whose book is no longer in the catalog, while Stop 3 repeats Stop 2's summary almost in full. Passage: "The plan is conformant. Read `lending/fines.py` and `lending/__main__.py` yourself, since both are in the critical zones. Mark the pull request ready when you want, which triggers your CI."

## What the developer would skip on the blueprint

Counted by the judge on the blueprint alone, lower being better: the facts the page says more than once in prose, the details of implementation that are not the developer's to decide, and the share of its words they could skip, in percent, which is an estimate. `count_grounded` is the share of the passages these counts rest on that stand on the page. The facts, the details and their passages are in the `count.json` of each run.

| | 01-overdue-list | 02-reservations | 03-overdue-reminders | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|---|---|
| `repeated_in_prose` | 3.5 (3 to 4) | 11 (9 to 13) | 5 (2 to 8) | 3 (1 to 5) | 5.5 (4 to 7) | 4 | 5.3333 (1 to 13) |
| `implementation_details` | 0.5 (0 to 1) | 2 (1 to 3) | 0.5 (0 to 1) | 3 | 1 (0 to 2) | 1 | 1.3333 (0 to 3) |
| `skippable_percent` | 10 | 12.5 (10 to 15) | 5 (0 to 10) | 7.5 (5 to 10) | 10 | 10 | 9.1667 (0 to 15) |
| `count_grounded` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## The judge, checked

| Spoiled document | Criterion | Original | Spoiled | Below |
|---|---|---|---|---|
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `blueprint.no-padding` | [4, 4] | [2, 2] | yes |
| a blueprint stripped of the two rules the interview settled, and of the ISBN left out | `blueprint.decidable` | [3, 4] | [2, 2] | yes |
| an interview with two questions the need and the code already answer | `interview.not-already-answered` | [5, 5] | [2, 2] | yes |

| Spoiled document | Count | Original | Spoiled | Above |
|---|---|---|---|---|
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `repeated_in_prose` | [0, 0] | [8, 7] | yes |
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `implementation_details` | [1, 0] | [10, 9] | yes |
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `skippable_percent` | [5, 0] | [45, 45] | yes |

## Cost

200 sessions, 30.89 USD at list price. The weekly gauge of the subscription rose by 6 points while they ran, every other use of the account included.

## What moved since the campaign before

- `02-reservations` `body_in_range`: 0 then 1, better.
- `02-reservations` `body_sections`: 6 then 4 (3 to 5), moved.
- `02-reservations` `criteria`: 9 then 11.5 (11 to 12), moved.
- `02-reservations` `planning_usd`: 2.2041 then 2.5103 (2.4207 to 2.6), worse.
- `02-reservations` `questions`: 3 then 6, moved.
- `02-reservations` `blueprint.diagrams`: 3 then 5, better.
- `02-reservations` `interview.not-already-answered`: 4 then 5, better.
- `02-reservations` `interview.right-number`: 3 then 4, better.
- `04-suspension` `planning_usd`: 1.0537 (1.0208 to 1.0867) then 1.1813 (1.1017 to 1.261), worse.
- `04-suspension` `questions`: 2.5 (2 to 3) then 4, moved.
- `04-suspension` `zones_none_said`: 1 then 0, worse.
- `04-suspension` `blueprint.diagrams`: 4 then 5, better.
- `04-suspension` `blueprint.no-padding`: 2 then 3, better.
- `04-suspension` `following.whose-turn`: 4 then 5, better.
- `04-suspension` `interview.right-number`: 5 then 4, worse.
- `04-suspension` `messages.clear`: 2 then 5, better.
- `04-suspension` `implementation_details`: 2 then 3, worse.
- `04-suspension` `skippable_percent`: 17.5 (15 to 20) then 7.5 (5 to 10), better.
- `05-fine-cap` `criteria`: 8.5 (8 to 9) then 11.5 (10 to 13), moved.
- `05-fine-cap` `diagram_as_expected`: 0 then 1, better.
- `05-fine-cap` `diagrams`: 1 then 0, moved.
- `05-fine-cap` `pr_described`: 0 then 1, better.
- `05-fine-cap` `blueprint.cut`: 3 then 4, better.
- `05-fine-cap` `blueprint.diagrams`: 3.5 (3 to 4) then 5, better.
- `05-fine-cap` `messages.clear`: 2 then 3.5 (3 to 4), better.
- `05-fine-cap` `messages.next-step`: 3 then 4, better.
- `05-fine-cap` `repeated_in_prose`: 1.5 (1 to 2) then 5.5 (4 to 7), worse.
- `06-borrow-limit` `usd`: 1.5325 then 1.9726 (1.5938 to 2.3514), worse.
- `06-borrow-limit` `following.no-noise`: 2 then 3, better.
- `06-borrow-limit` `following.whose-turn`: 4 then 5, better.
- `06-borrow-limit` `following.why-stopped`: 5 then 4, worse.
- `06-borrow-limit` `messages.clear`: 2 then 4.5 (4 to 5), better.
- `06-borrow-limit` `messages.next-step`: 3 then 5, better.
- `06-borrow-limit` `repeated_in_prose`: 6 (5 to 7) then 4, better.
- `06-borrow-limit` `skippable_percent`: 15 then 10, better.
- `all` `messages.clear`: 2 then 4.375 (3 to 5), better.
