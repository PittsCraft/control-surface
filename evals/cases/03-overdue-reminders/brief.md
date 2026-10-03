# Brief: the overdue reminders

What I know about this need and did not write in it.

## Rules

- Overdue means what it means today: an open loan whose due date is before today. A loan due
  today is not overdue, and a returned loan never is, even when it came back late.
- One notice per member, whatever the number of their overdue loans. `to` is the member id,
  `kind` is `reminder`, `on` is today.
- The text names the overdue books of the member by id, and only those: not the other books the
  member holds. The total is the sum of the fines of these overdue loans as of today.
- In the printed line, `<number of loans>` is the number of overdue loans of the member, and
  `<total fine>` is the same total as in the notice, with two decimals.
- A member with nothing overdue gets nothing: no notice, no line.
- A member is reminded again only 7 days or more after their last reminder. Reminded on the 1st,
  they are reminded again from the 8th; on the 7th, nothing.
- A member skipped because their last reminder is too recent prints no line.
- How the command knows a member was already reminded: it looks in the outbox itself, at the
  `reminder` notices already there for that member. No new file, no new field, and `loans.jsonl`
  is not touched. The mailer sends the notices but never removes a line from `outbox.jsonl`.
- Only the notices of kind `reminder` count. A `fine` notice queued for the member yesterday
  does not delay their reminder.
- The command always exits 0. When nobody is reminded it prints nothing.
- `remind` takes no argument, and the 7 days are fixed in the code.
- The fine computation does not change, and `remind` calls it instead of computing its own.
- The order of the printed lines: by member id is fine, I do not rely on it.

## Not mine to decide

- The wording of the notice, beyond the book ids and the total.
- Which module holds the reminders, and the names of the functions.
- How the outbox is read back.
- How the tests are laid out.
