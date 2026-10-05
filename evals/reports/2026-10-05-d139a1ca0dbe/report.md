# Evaluation of the chain

Chain `d139a1ca0dbe`, measured on 2026-10-05T10:58:28Z: 7 runs over 4 cases. A value is the mean over the runs of a case, with its lowest and highest when they differ; a truth counts 1. An empty cell does not apply.

4 of these runs played planning alone, on purpose: they went no further than the hand over, and nothing was approved or built in them. No measure of the execution counts them, here or against another campaign, and what the judge says of their stops is kept apart, under the dimensions that end in `-in-planning`.

## Does it meet its goals

| | 02-reservations | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|
| `handed_over` | 1 | 1 | 1 | 1 | 1 |
| `conformant` |  | 1 | 1 | 1 | 1 |
| `acceptance` |  | 1 | 1 | 1 | 1 |
| `approved_by_sentence` | 0 | 0 | 0 | 0 | 0 |
| `questions` | 3 | 2.5 (2 to 3) | 1 | 2.5 (2 to 3) | 2.1429 (1 to 3) |
| `corrections` | 0 | 0 | 0 | 0.5 (0 to 1) | 0.1429 (0 to 1) |
| `planning_passes` | 0 | 0 | 0 | 0 | 0 |
| `reviews` |  | 1 | 1 | 1 | 1 |
| `fixes` |  | 0 | 0 | 0 | 0 |
| `pr_draft_at_hand_over` | 1 | 1 | 1 | 1 | 1 |
| `pr_described` | 1 | 0.5 (0 to 1) | 0 | 1 | 0.5 (0 to 1) |
| `pr_refreshed` |  | 1 | 1 | 1 | 1 |
| `pr_marked_ready` |  | 0 | 0 | 0 | 0 |
| `gh_not_played` | 0 | 0 | 0 | 0 | 0 |
| `zones_named` |  |  | 1 |  | 1 |
| `zones_none_said` | 1 | 1 |  | 1 | 1 |
| `zones_files_listed` |  | 1 | 1 | 1 | 1 |
| `zones_consistent` |  | 1 | 1 | 1 | 1 |
| `frame` | 1 | 1 | 1 | 1 | 1 |
| `body_sections` | 6 | 3 | 1.5 (1 to 2) | 1 | 2.4286 (1 to 6) |
| `body_in_range` | 0 | 1 | 0.5 (0 to 1) | 1 | 0.7143 (0 to 1) |
| `diagrams` | 3 | 1.5 (1 to 2) | 1 | 1 | 1.4286 (1 to 3) |
| `diagram_as_expected` | 1 |  | 0 | 0 | 0.2 (0 to 1) |
| `cut_kept` | 1 |  |  | 1 | 1 |
| `plan_minimum` | 1 | 1 | 1 | 1 | 1 |
| `contaminated` | 0 | 0 | 0 | 0 | 0 |
| `planning_usd` | 2.2041 | 1.0537 (1.0208 to 1.0867) | 1.0219 (1.0037 to 1.0402) | 1.2767 (0.9386 to 1.6147) | 1.2727 (0.9386 to 2.2041) |
| `usd` |  | 1.8757 | 1.8527 | 1.5325 | 1.7536 (1.5325 to 1.8757) |

Outcomes: `02-reservations` stopped-at-hand-over; `04-suspension` conformant, stopped-at-hand-over; `05-fine-cap` conformant, stopped-at-hand-over; `06-borrow-limit` stopped-at-hand-over, conformant.

## Is it good to work with

Scores from 1 to 5, by the judge.

| | 02-reservations | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|
| `blueprint.cut` | 4 | 3.5 (3 to 4) | 3 | 3.5 (3 to 4) | 3.4286 (3 to 4) |
| `blueprint.decidable` | 4 | 4 | 4.5 (4 to 5) | 5 | 4.4286 (4 to 5) |
| `blueprint.diagrams` | 3 | 4 | 3.5 (3 to 4) | 4.5 (4 to 5) | 3.8571 (3 to 5) |
| `blueprint.no-padding` | 2 | 2 | 2 | 2 | 2 |
| `following-in-planning.no-noise` | 2 | 2 | 3 | 2 | 2.25 (2 to 3) |
| `following-in-planning.whose-turn` | 5 | 5 | 5 | 5 | 5 |
| `following-in-planning.why-stopped` | 5 | 4 | 5 | 4 | 4.5 (4 to 5) |
| `following.no-noise` |  | 3 | 3 | 2 | 2.6667 (2 to 3) |
| `following.whose-turn` |  | 4 | 5 | 4 | 4.3333 (4 to 5) |
| `following.why-stopped` |  | 5 | 5 | 5 | 5 |
| `grounded` | 1 | 1 | 1 | 1 | 1 |
| `interview.no-invented-rule` | 4 | 4 | 5 | 4 | 4.2857 (4 to 5) |
| `interview.not-already-answered` | 4 | 5 | 5 | 4.5 (4 to 5) | 4.7143 (4 to 5) |
| `interview.questions-matter` | 4 | 5 | 5 | 3 | 4.2857 (3 to 5) |
| `interview.right-number` | 3 | 5 | 5 | 3.5 (3 to 4) | 4.2857 (3 to 5) |
| `messages-in-planning.clear` | 3 | 2 | 2 | 2 | 2.25 (2 to 3) |
| `messages-in-planning.next-step` | 5 | 4 | 4 | 4 | 4.25 (4 to 5) |
| `messages-in-planning.right-length` | 3 | 4 | 3 | 4 | 3.5 (3 to 4) |
| `messages.clear` |  | 2 | 2 | 2 | 2 |
| `messages.next-step` |  | 3 | 3 | 3 | 3 |
| `messages.right-length` |  | 3 | 4 | 4 | 3.6667 (3 to 4) |

The lowest score of each criterion, with the judge's reason and its passage:

- `blueprint.cut`, 3 in `04-suspension`: The two behaviors each get their own section, titled in the feature's words. But a section about where the code lives comes before both, against the order in which the developer would discover the feature. Passage: "## Where the amount owed lives"
- `blueprint.decidable`, 4 in `02-reservations`: The interview answers are all carried with the 5-day amendment, and the record shape, the notice text and the borrow-without-dates assumption are stated. One detail is missing: criterion 3 does not say whether a refused `cancel` gives its reason on standard error, as criterion 2 does for `reserve`. Passage: "When the member is not in that queue, it is refused with exit 1."
- `blueprint.diagrams`, 3 in `02-reservations`: The state diagram earns its place, and the module graph shows real relations. The return sequence diagram, though, is a near-linear chain with optional steps that the surrounding prose already conveys. Passage: "CLI->>Holds: hold B1 for the first member of its queue"
- `blueprint.no-padding`, 2 in `02-reservations`: Several passages could be skipped: the module split and its circular-import rationale are implementation, not the developer's call, and the assumption that holds never expire on the date alone is stated twice. The opening sentence also restates the need without adding to it. Passage: "Putting everything in one module would create a circular import, since that module would need `loans.py` while `loans.py` needs it."
- `following-in-planning.no-noise`, 2 in `02-reservations`: Chain mechanics are narrated for their own sake ('specs.md is verbatim, and I replaced no paths'). The same reassurance about committing, pushing and the cross-check finding no omissions comes back at stops 4 and 5, together with the repeated gate and blueprint path. Passage: "It is committed and pushed, the pull request description is refreshed, and the cross-check found no omissions."
- `following-in-planning.whose-turn`, 5 in `02-reservations`: Every stop ends by saying plainly what the developer must do next: pick an option, amend, or launch `/surface-execute`. Stop 6 makes clear that a casual 'go ahead' is not their approval and names the one action that is. Passage: "That reply doesn't approve the plan, and I've recorded nothing. Only launching `/surface-execute` approves revision 2."
- `following-in-planning.why-stopped`, 4 in `04-suspension`: Each stop states its reason: a question, the hand over of the drafted plan, or the hand back after a reply that approves nothing. However, Stop 3 ends the interview without saying why the promised question about what `owed` prints for an unknown member was never asked. Passage: "The plan is drafted and pushed, and the draft pull request is open at https://github.com/stand-in/lending/pull/1."
- `following.no-noise`, 2 in `06-borrow-limit`: Several stops narrate the chain for its own sake: the cross-check result and the gate the loop will run at stop 4, and the push, description refresh and test count at stop 6. Stop 6 also adds reassurance that the reviewer proved everything. Passage: "The cross-check found no omissions."
- `following.whose-turn`, 4 in `04-suspension`: Every stop makes the developer's turn clear: answer the question, amend, or launch `/surface-execute`. At the final stop the expected action blurs, mixing 'mark it ready', 'read' the zone, and an optional 'say so' about narrowing the zone, without saying which of these the developer needs to do. Passage: "If you read that zone as covering only the two format functions, say so and the list can be dropped."
- `following.why-stopped`, 5 in `04-suspension`: Each stop names its reason. Stops 1–3 end on a numbered question, stop 4 hands over for approval, stop 5 explains why the reply did not approve the plan, and stop 6 reports the work done with gate and review results. Passage: "The plan is conformant: both slices are done, the gate passes (43 tests), and the review found no defects, deviations or breaks."
- `interview.no-invented-rule`, 4 in `02-reservations`: Nearly every rule traces back to the need, an answer or the code, and the one about holds not expiring by date is flagged as an assumption. The wording of the `hold` notice, which reaches real members, came from the plan alone. The blueprint lists it as something the developer might miss, not as an assumption to confirm. Passage: "{\"to\": \"M2\", \"kind\": \"hold\", \"text\": \"B1 is held for you until 2026-03-10.\", \"on\": \"2026-03-05\"}"
- `interview.not-already-answered`, 4 in `02-reservations`: No question repeats the need outright. But Q1 puts the refusal of an unknown book or member into its options as if it were open, and the README already settles that ('An unknown book or member is refused'). Passage: "Unknown book or member is refused, as `borrow` does."
- `interview.questions-matter`, 3 in `06-borrow-limit`: Q1 is a real business rule that only the developer could set, and their answer changed the limits. Q2 asks about the internal order of the checks, which the developer said was not theirs to decide, so it should have been an implementation decision rather than a question. Passage: "Answer (2026-10-05): \"That's the assistant's call, since the order of the checks isn't mine to decide. I'll take your recommendation, A.\""
- `interview.right-number`, 3 in `02-reservations`: One question is missing: whether a holder can still borrow after the hold's last day when nobody has run `expire`. That is a visible business rule, and it was filled by a guess, even though the guess is disclosed. Meanwhile part of Q3 spent a question on output wording the developer did not care about. Passage: "If the holder comes on D+7 and nobody has run `expire` yet, they can still borrow the book, and other members are still refused. This keeps `borrow` free of any clock. The plan made this assumption without asking the developer."
- `messages-in-planning.clear`, 2 in `04-suspension`: Stop 3 speaks in the chain's own vocabulary: an 'extractor', a 'cross-check', a 'gate' the 'loop' will run, none of which the developer can act on. Stop 4 then promises 'two slices' when Stop 3 described a shared first section plus two flows. Passage: "The extractor cut it that way because both flows use that one amount."
- `messages-in-planning.next-step`, 4 in `04-suspension`: Stops 2, 3 and 4 each end on the right step: answer the question, amend or launch `/surface-execute`, or launch it. Stop 1 instead ends on a list of later questions, so the question the developer must answer now gets buried above it. Passage: "Still to ask after this: - the limit itself; - whether reaching it or only exceeding it blocks `borrow`; - what `owed` prints for an unknown member."
- `messages-in-planning.right-length`, 3 in `02-reservations`: The hand-over message spends a paragraph on how the blueprint is laid out. That is the file the developer is sent to read, so the paragraph repeats it. The other messages fit what they have to say. Passage: "The body of the blueprint is cut by flow. The shared reservation and hold data comes first. Then there is one section each for reserving and cancelling, a book coming back, borrowing a held book, and `expire`, and last where the rules live."
- `messages.clear`, 2 in `04-suspension`: The later messages lean on the chain's internal vocabulary ("cross-check", "gate", "slices", "conformant", "critical zones", "deviations or breaks"), and Stop 5's "two slices" contradicts Stop 4's three-part cut. Stop 6 also says that, read narrowly, no critical zone was touched, while the PR body says the branch changed files inside the critical zones. Passage: "If you read that zone as covering only the two format functions, say so and the list can be dropped. Read in that narrow way, no critical zone was touched."
- `messages.next-step`, 3 in `04-suspension`: Stop 6 ends on file locations rather than on the developer's step (read `lending/loans.py:81-88`, then mark the PR ready), which sits buried mid-message. Stop 1 also closes on questions still to come instead of on the answer it is waiting for. Passage: "The review is in `docs/plans/2026-10-05-fine-limit/reviews/pass-01.md` and the proof of conformity in `docs/plans/2026-10-05-fine-limit/conformity.md`."
- `messages.right-length`, 3 in `04-suspension`: Most messages are tight, but Stop 6 spends a convoluted paragraph explaining why the reviewer listed `lending/loans.py`. That is reviewer reasoning the developer cannot act on, and it buries the one useful pointer (lines 81-88). Passage: "The reviewer listed it because that file also holds the `loans.jsonl` format functions (`load_loans` and `save_loans`), which have no diff. `lending/fines.py` is untouched."

## What the developer would skip on the blueprint

Counted by the judge on the blueprint alone, lower being better: the facts the page says more than once in prose, the details of implementation that are not the developer's to decide, and the share of its words they could skip, in percent, which is an estimate. `count_grounded` is the share of the passages these counts rest on that stand on the page. The facts, the details and their passages are in the `count.json` of each run.

| | 02-reservations | 04-suspension | 05-fine-cap | 06-borrow-limit | all |
|---|---|---|---|---|---|
| `repeated_in_prose` | 9 | 4 (3 to 5) | 1.5 (1 to 2) | 6 (5 to 7) | 4.5714 (1 to 9) |
| `implementation_details` | 2 | 2 | 1 | 1.5 (1 to 2) | 1.5714 (1 to 2) |
| `skippable_percent` | 15 | 17.5 (15 to 20) | 12.5 (10 to 15) | 15 | 15 (10 to 20) |
| `count_grounded` | 1 | 1 | 1 | 1 | 1 |

## The judge, checked

| Spoiled document | Criterion | Original | Spoiled | Below |
|---|---|---|---|---|
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `blueprint.no-padding` | [3] | [2, 2] | yes |
| a blueprint stripped of the two rules the interview settled, and of the ISBN left out | `blueprint.decidable` | [4, 4] | [2, 2] | yes |
| an interview with two questions the need and the code already answer | `interview.not-already-answered` | [4] | [2, 2] | yes |

| Spoiled document | Count | Original | Spoiled | Above |
|---|---|---|---|---|
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `repeated_in_prose` | [0, 0] | [5, 7] | yes |
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `implementation_details` | [0, 0] | [7, 10] | yes |
| a blueprint padded with the need restated, a walk through the code, a diagram of a chain with no branch and the list of the tests | `skippable_percent` | [0, 0] | [45, 45] | yes |

## Cost

108 sessions, 14.23 USD at list price. The weekly gauge of the subscription rose by 2 points while they ran, every other use of the account included.

## What moved since the campaign before

- `02-reservations` `body_sections`: 7 then 6, moved.
- `02-reservations` `criteria`: 14 then 9, moved.
- `02-reservations` `planning_usd`: 2.6054 then 2.2041, better.
- `02-reservations` `questions`: 4 then 3, moved.
- `02-reservations` `words`: 2296 then 1448, moved.
- `02-reservations` `blueprint.cut`: 3 then 4, better.
- `02-reservations` `blueprint.diagrams`: 4 then 3, worse.
- `02-reservations` `interview.not-already-answered`: 5 then 4, worse.
- `02-reservations` `interview.questions-matter`: 5 then 4, worse.
- `02-reservations` `interview.right-number`: 4 then 3, worse.
- `02-reservations` `count_grounded`: 0.9863 then 1, moved.
- `02-reservations` `implementation_details`: 11 then 2, better.
- `02-reservations` `repeated_in_prose`: 19 then 9, better.
- `02-reservations` `skippable_percent`: 35 then 15, better.
- `04-suspension` `body_sections`: 4 then 3, moved.
- `04-suspension` `planning_usd`: 1.1131 then 1.0537 (1.0208 to 1.0867), better.
- `04-suspension` `usd`: 1.9699 then 1.8757, better.
- `04-suspension` `words`: 1113 then 928.5 (858 to 999), moved.
- `04-suspension` `blueprint.decidable`: 5 then 4, worse.
- `04-suspension` `following.no-noise`: 2 then 3, better.
- `04-suspension` `interview.no-invented-rule`: 5 then 4, worse.
- `04-suspension` `messages.clear`: 3 then 2, worse.
- `04-suspension` `messages.next-step`: 2 then 3, better.
- `04-suspension` `implementation_details`: 7 then 2, better.
- `04-suspension` `repeated_in_prose`: 13 then 4 (3 to 5), better.
- `04-suspension` `skippable_percent`: 30 then 17.5 (15 to 20), better.
- `05-fine-cap` `body_sections`: 3 then 1.5 (1 to 2), moved.
- `05-fine-cap` `diagrams`: 2 then 1, moved.
- `05-fine-cap` `usd`: 1.8687 then 1.8527, better.
- `05-fine-cap` `words`: 1113 then 780 (684 to 876), moved.
- `05-fine-cap` `blueprint.cut`: 4 then 3, worse.
- `05-fine-cap` `following.no-noise`: 2 then 3, better.
- `05-fine-cap` `interview.no-invented-rule`: 4 then 5, better.
- `05-fine-cap` `interview.right-number`: 4 then 5, better.
- `05-fine-cap` `messages.right-length`: 3 then 4, better.
- `05-fine-cap` `implementation_details`: 5 then 1, better.
- `05-fine-cap` `repeated_in_prose`: 8 then 1.5 (1 to 2), better.
- `05-fine-cap` `skippable_percent`: 25 then 12.5 (10 to 15), better.
- `06-borrow-limit` `planning_usd`: 0.8492 then 1.2767 (0.9386 to 1.6147), worse.
- `06-borrow-limit` `questions`: 1 then 2.5 (2 to 3), moved.
- `06-borrow-limit` `usd`: 1.5302 then 1.5325, worse.
- `06-borrow-limit` `following.no-noise`: 3 then 2, worse.
- `06-borrow-limit` `interview.no-invented-rule`: 5 then 4, worse.
- `06-borrow-limit` `interview.questions-matter`: 5 then 3, worse.
- `06-borrow-limit` `interview.right-number`: 5 then 3.5 (3 to 4), worse.
- `06-borrow-limit` `messages.clear`: 3 then 2, worse.
- `06-borrow-limit` `messages.right-length`: 3 then 4, better.
- `06-borrow-limit` `implementation_details`: 5 then 1.5 (1 to 2), better.
- `06-borrow-limit` `skippable_percent`: 25 then 15, better.
- `all` `implementation_details`: 7.8333 (5 to 12) then 1.5714 (1 to 2), better.
