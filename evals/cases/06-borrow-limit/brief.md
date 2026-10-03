# Brief: the borrow limit

What I know about this need and did not write in it.

## Rules

- The limit is on open loans, the books a member holds right now: at most 3 for a student, at
  most 6 for staff.
- The category is the one of the member in `members.jsonl`. There are only these two.
- The limit is checked when a member borrows. The `borrow` that would take the member above
  their limit is refused like the other refusals of `borrow`: a reason on standard error, exit
  code 1, no loan recorded. A student with 3 open loans cannot borrow a 4th; with 2, the 3rd
  passes. Staff with 6 open loans cannot borrow a 7th; with 5, the 6th passes.
- Returned loans do not count, however many there are.
- Returning a book frees a place at once: the next `borrow` of the member passes.
- Some members are already above the limit today (a few students hold 5 books). Their loans stay
  as they are: nothing is closed, shortened or flagged. They just cannot borrow again until they
  are back under their limit.
- The limit is per member: a member at their limit does not stop another one from borrowing.
- The two numbers are fixed in the code. No option on the command line, no configuration file,
  no exception for one member.
- Nothing else changes: no new command, no new file, no new field in a loan line, no notice, and
  a `borrow` that passes prints the same line as today.
- The wording of the refusal is free, as long as it tells the desk the member holds too many
  books.

## Not mine to decide

- Where the check and the two numbers live in the code.
- The names of the functions and of the constants.
- The order of this check among the other checks of `borrow`.
- How the tests are laid out.
