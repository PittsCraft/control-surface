# Brief: the grace days and the cap

What I know about this need and did not write in it.

## Rules

- The rate does not change: 0.25 per day, for each day late after the first 2. A loan 1 or 2
  days late owes 0.00, 3 days late 0.25, 10 days late 2.00.
- The days late are counted as today: from the day after the due date to today, or to the return
  date once the book is back.
- The grace applies to every loan, the old ones included: a loan borrowed before the change gets
  its 2 days too. Nothing of the old rule is kept.
- The cap is the price of the book of the loan, read from `books.jsonl`. Each loan is capped by
  its own book. A fine that reaches the price stays at the price, however late the loan is; a
  fine below the price is untouched.
- A book with no known price is not capped: its fine keeps growing. That is a book whose line
  has no `price`, we have a few old ones. A loan whose book is no longer in the catalog is not
  capped either.
- Amounts keep two decimals everywhere, also when the cap applies and the price was typed as
  `3.5`: the fine prints `3.50`.
- The `fine` notice queued on a late return follows the new rule: it carries the same amount as
  the one `return` prints, and no notice is queued when the new fine is zero.
- The fine computation stays pure, as the README says: it reads no file, so it does not look the
  price up itself. The price is given to it.
- No new command, no new option, no new file, no new field. `loans.jsonl` does not change.
- Nothing is stored about fines, so there is nothing to migrate.

## Not mine to decide

- The signature of the fine function and how the price reaches it.
- The names of the constants for the grace and the rate.
- Which module looks the price up.
- How the tests are laid out.
