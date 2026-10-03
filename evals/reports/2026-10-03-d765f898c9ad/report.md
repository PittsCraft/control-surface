# Evaluation of the chain

Chain `d765f898c9ad`, measured on 2026-10-03T21:39:49Z: 5 runs over 3 cases. A value is the mean over the runs of a case, with its lowest and highest when they differ; a truth counts 1. An empty cell does not apply.

## Does it meet its goals

| | 01-overdue-list | 02-reservations | 03-overdue-reminders | all |
|---|---|---|---|---|
| `handed_over` | 1 | 1 | 1 | 1 |
| `conformant` | 0.5 (0 to 1) | 1 | 1 | 0.8 (0 to 1) |
| `acceptance` | 1 | 1 | 1 | 1 |
| `approved_by_sentence` | 0 | 0 | 0 | 0 |
| `questions` | 2 | 4 | 0 | 1.6 (0 to 4) |
| `corrections` | 1 | 0 | 1 | 0.8 (0 to 1) |
| `planning_passes` | 1 (0 to 2) | 0 | 0 | 0.4 (0 to 2) |
| `reviews` | 1 | 1 | 1 | 1 |
| `fixes` | 0 | 0 | 0 | 0 |
| `zones_none_said` | 1 | 1 | 1 | 1 |
| `zones_files_listed` | 1 | 1 | 1 | 1 |
| `zones_consistent` | 1 | 1 | 1 | 1 |
| `frame` | 1 | 1 | 1 | 1 |
| `body_sections` | 1.5 (1 to 2) | 5 | 1 | 2 (1 to 5) |
| `body_in_range` | 0.5 (0 to 1) | 1 | 0 | 0.4 (0 to 1) |
| `diagrams` | 1 | 3 | 1 | 1.4 (1 to 3) |
| `diagram_as_expected` | 0 | 1 | 1 | 0.6 (0 to 1) |
| `cut_kept` | 0.5 (0 to 1) | 1 | 1 | 0.8 (0 to 1) |
| `plan_minimum` | 1 | 1 | 1 | 1 |
| `contaminated` | 0 | 0 | 0 | 0 |
| `usd` | 3.4204 (2.2259 to 4.6149) | 4.2718 | 2.9079 (2.8248 to 2.991) | 3.3857 (2.2259 to 4.6149) |

Outcomes: `01-overdue-list` handed-back, conformant; `02-reservations` conformant; `03-overdue-reminders` conformant, conformant.

## Is it good to work with

Scores from 1 to 5, by the judge.

| | 01-overdue-list | 02-reservations | 03-overdue-reminders | all |
|---|---|---|---|---|
| `blueprint.cut` | 3 (2 to 4) | 3 | 3 | 3 (2 to 4) |
| `blueprint.decidable` | 4.5 (4 to 5) | 4 | 5 | 4.6 (4 to 5) |
| `blueprint.diagrams` | 4 (3 to 5) | 3 | 3.5 (3 to 4) | 3.6 (3 to 5) |
| `blueprint.no-padding` | 2 | 2 | 2 | 2 |
| `following.no-noise` | 2 | 2 | 2 | 2 |
| `following.whose-turn` | 4.5 (4 to 5) | 4 | 5 | 4.6 (4 to 5) |
| `following.why-stopped` | 5 | 5 | 5 | 5 |
| `grounded` | 1 | 1 | 1 | 1 |
| `interview.no-invented-rule` | 4 | 4 | 3 (2 to 4) | 3.6 (2 to 4) |
| `interview.not-already-answered` | 4.5 (4 to 5) | 5 | 5 | 4.8 (4 to 5) |
| `interview.questions-matter` | 4 (3 to 5) | 4 | 2.5 (2 to 3) | 3.4 (2 to 5) |
| `interview.right-number` | 4 (3 to 5) | 4 | 1.5 (1 to 2) | 3 (1 to 5) |
| `messages.clear` | 2.5 (2 to 3) | 2 | 2 | 2.2 (2 to 3) |
| `messages.next-step` | 4.5 (4 to 5) | 3 | 3.5 (3 to 4) | 3.8 (3 to 5) |
| `messages.right-length` | 3.5 (3 to 4) | 3 | 3 | 3.2 (3 to 4) |

The lowest score of each criterion, with the judge's reason and its passage:

- `blueprint.cut`, 2 in `01-overdue-list`: One section titled for the example output holds unrelated matters: module design, the missing file, extra arguments, tie ordering, and help and README text. None of these gets its own section in the order the developer would meet it. The behaviors the developer decides separately, such as ties, usage errors and documentation, are not cut apart. Passage: "## The overdue list at the desk"
- `blueprint.decidable`, 4 in `01-overdue-list`: The blueprint carries every rule and interview answer: text-ordered ties, the empty or missing file, and exit 2 on an extra argument. One lapse of detail: criterion 8 says listing 'always ends with exit code 0' while exit 2 for wrong usage only appears later in prose, so the contract reads as self-contradictory on its own. Passage: "The command takes no argument of its own and never refuses: listing the loans always ends with exit code 0, never 1."
- `blueprint.diagrams`, 3 in `01-overdue-list`: The single flowchart does show several modules in relation, including the existing import between them. But what it shows is internal module wiring that serves an implementation argument, not a behavior the developer decides, so it stands where no decision needs it. Passage: "fines -.->|already imports| loans"
- `blueprint.no-padding`, 2 in `01-overdue-list`: Several facts appear three times: a `--today` after `overdue` being ignored, a misspelled `--today` before it exiting 2, `B10` before `B2`, and the parsing reaching every command each recur across the criteria, the "In practice" bullets and "Sensitive zones". The page also carries implementation detail that is not the developer's to decide, such as the Python 3.11 library behaviour, the rejected parsing alternatives and the reason why `loans.py` cannot sort. Passage: "A `--today` written after `overdue` is ignored without a word, and the listing then uses the real date. Only what follows the command is ignored: a misspelled `--today` before it still exits 2 (criterion 10). See \"Extra arguments and exit c [...]"
- `following.no-noise`, 2 in `01-overdue-list`: The missing `gh` and the absent pull request are reported at three stops, and the chain's internals are narrated for their own sake: the drafting agent's stray sentence, its later removal, and "the third check found no omissions". Reassurances such as "no code has been written yet" add nothing the developer needs. Passage: "Revision 2 is drafted and cross-checked, and the third check found no omissions. It's committed and pushed to `feat/overdue-command`. `gh` isn't installed, so there is still no pull request, and no code has been written yet."
- `following.whose-turn`, 4 in `01-overdue-list`: Every stop makes the developer's turn clear, and most say exactly what to do. Stop 3 is the exception: it lays out options A and B but never asks for a pick, ending only on a side question about scope. Passage: "Errors raised before the command is chosen, such as a malformed `--today` or a missing command, belong to the whole tool and keep exiting 2, as the README says. Tell me if you meant something wider."
- `following.why-stopped`, 5 in `01-overdue-list`: Each stop names its reason: a question at stops 1 and 3, a plan ready for approval at stops 2 and 4, a non-approving reply at stop 5, and a plan change proposal at stop 6. There is no lapse. Passage: "The loop has stopped on a plan change proposal, and it's your turn."
- `interview.no-invented-rule`, 2 in `03-overdue-reminders`: The blueprint states rules as settled that come from no source. A member unknown to the library is still reminded, although the README says an unknown member is refused. A reminder dated after today counts as recent. The member order and the wording of the notice appear as criteria, not as assumptions to confirm. Passage: "The member ids come from `loans.jsonl` alone: `members.jsonl` is not read, so a member id unknown there is still reminded, and the command never refuses."
- `interview.not-already-answered`, 4 in `01-overdue-list`: The code already settles Q2: argparse rejects an unknown argument with exit 2, and the README gives 2 as the wrong-usage code. Asking was still justified only because the amendment cast doubt on that, so this is a small lapse rather than a redundant question. Passage: "The command line is built on `argparse`, which rejects an unknown argument with exit code 2, the \"wrong usage\" code of the README."
- `interview.questions-matter`, 2 in `03-overdue-reminders`: The interview asked no questions, so it never brought out the one rule only the developer knew: how often a member may be reminded. The developer had to correct that rule in an amendment after reading the blueprint, and the contract with the mailer was also left unasked. Passage: "None. The specs and the code settle every rule a member or a program reading the outbox would see"
- `interview.right-number`, 1 in `03-overdue-reminders`: Zero questions was too few. The reminder cadence was guessed as once a day and only fixed by a later amendment, and whether the mailer accepts the new `reminder` kind was never asked. Passage: "The mailer, which reads the outbox, will find lines of a kind it has never received, `reminder`, and every line it sends reaches a real member. The plan does not look at the mailer."
- `messages.clear`, 2 in `01-overdue-list`: Several messages use the chain's internal vocabulary instead of plain words. Stop 2 says "Cut", "Gates", "Critical zones", "the drafting agent" and "cross-checked with no omissions"; Stop 4 says "the third check"; Stop 6 says "slice 1", "the loop", "the gate", "contract break" and "A fixer". Passage: "- **Cut:** the blueprint has one section, \"Listing the late loans\", because this is a small change with a single behavior."
- `messages.next-step`, 3 in `02-reservations`: Stops 1 to 7 each end on the right step: answer the question, amend, or launch `/surface-execute`. The final message ends on a remark that the critical zones are untouched, and the real next step, opening the pull request and marking it ready, is buried in the middle. Passage: "Here there are none: `lending/fines.py` and the `loans.jsonl` format are untouched."
- `messages.right-length`, 3 in `01-overdue-list`: The developer gave a custom answer to Q1 (ties by book id as text, no member-id rule), but Stop 2 never confirms how the plan recorded it. Stop 4, by contrast, restates each change it made. Passage: "The plan is drafted, committed and pushed to `feat/overdue-command`. It is waiting for your approval."

## Cost

65 sessions, 18.31 USD at list price. The weekly gauge of the subscription rose by 5 points while they ran, every other use of the account included.

## What moved since the campaign before

- `01-overdue-list` `questions`: 1 then 2, moved.
- `03-overdue-reminders` `words`: 1309.67 (1235 to 1425) then 945.5 (905 to 986), moved.
- `03-overdue-reminders` `blueprint.cut`: 4 then 3, worse.
- `03-overdue-reminders` `messages.clear`: 3 then 2, worse.
