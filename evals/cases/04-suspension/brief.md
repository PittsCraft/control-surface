# Brief: suspending the members who owe too much

What I know about this need and did not write in it.

## Rules

- What a member owes is the sum of the fines of their open loans as of today. It is computed on
  the spot, each time it is needed. Nothing is stored: no new file, no new field in an existing
  file, no flag on the member.
- The fine of each loan is the existing computation. It does not change.
- Returned loans do not count: their fine was settled at the desk when the book came back.
- The threshold is 10.00. A member is suspended when they owe more than 10.00. At exactly 10.00
  they can still borrow.
- The `borrow` of a suspended member is refused: a reason on standard error, exit code 1, no
  loan recorded.
- Staff are suspended like students: same rule, same threshold.
- Returning books lifts the suspension by itself: once the late books are back, their loans no
  longer count and the next `borrow` passes. There is no command to lift a suspension and no
  waiting time.
- A member is judged on their own loans only: a suspended member does not stop another one.
- Suspension only stops `borrow`. A suspended member can still return books, and their loans are
  still listed.
- A new command, `owed <member>`, prints what the member owes as of today: the amount with two
  decimals and nothing else on the line, like `fine` does. For a member who owes nothing it
  prints `0.00`. An unknown member is refused, exit code 1.
- `owed` prints the amount whether or not the member is suspended. It does not print the word
  suspended, nor the threshold.
- The threshold is fixed in the code: no option, no configuration.
- No notice is queued when a `borrow` is refused.

## Not mine to decide

- Where the policy lives: a new module or an existing one.
- The names of the functions and of the constant.
- The wording of the refusal.
- The order of this check among the other checks of `borrow`.
- How the tests are laid out.
