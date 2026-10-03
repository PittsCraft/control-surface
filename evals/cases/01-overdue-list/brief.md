# Brief: the overdue list

What I know about this need and did not write in it.

## Rules

- Order: the loan with the most days late comes first. Two loans late by the same number of days
  are ordered by book id, compared as text (`B1` before `B2`).
- Days late are counted the way the fine counts them: from the day after the due date to today.
  A loan due yesterday is 1 day late.
- A loan due today is not overdue: it is not listed.
- A returned loan is never listed, even when it came back late.
- When nothing is overdue, the command prints nothing and exits 0. Same when there is no loan at
  all, or no `loans.jsonl` yet.
- The command always exits 0: there is nothing to refuse.
- It lists the loans of every member. No filter by member, nobody asked for one.
- It only reads: no file changes and no notice is queued.
- `<due>` is printed like the `loans` command prints it, `YYYY-MM-DD`. `<days late>` is a whole
  number, with no unit.
- The existing commands do not change.

## Not mine to decide

- Where the sort lives, in the command line or in a domain module.
- Function names, and whether the existing `overdue` function of `lending/loans.py` is reused.
- How the tests are laid out.
- The help text of the command.
