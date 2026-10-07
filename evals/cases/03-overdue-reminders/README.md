# The overdue reminders: a need that states the wrong rule

This case states the wrong rule in its need, on purpose. Do not repair it.

`need.md`, what the developer types, says: "No member is reminded twice on the same day." `brief.md`, what they know and did not write, says what they mean: a member is reminded again only 7 days or more after their last reminder.

The need reads as complete, so a session that takes it at its word asks nothing about it and plans the same-day rule. No interview could be blamed for that: nothing was left open. The developer finds the error when they read the blueprint, which states the rule plainly enough to be contradicted, and sends it back with the rule they meant.

That is what the case evaluates: an error of the need is caught at the reading of the blueprint, before any code, and the next revision carries the right rule. The acceptance tests hold the 7 days, so a run whose blueprint hid the rule, or lost the correction, fails them.

So one correction is expected in every run of this case. `case.json` says so under `expected_correction`, with the words that tell that correction among those the developer sends back. The harness reads it there: the report gives it as `expected_correction` and leaves it out of `corrections`, which counts the rules an interview did not ask for and the plan guessed.
