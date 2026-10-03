Members want to reserve a book that is out on loan. Add reservations:

- `reserve <book> <member>` puts the member in the queue of the book, first come first served.
- `cancel <book> <member>` takes the member out of the queue.
- On `return`, the first member of the queue gets a notice in the outbox with `kind` `hold`, and
  the book is held for them. While a book is held, only that member can borrow it.
- `expire` drops the holds that were not picked up in time and passes each one to the next
  member of the queue, with a new `hold` notice. A hold lasts 3 days.

Reservations live in a new file of the data directory, `reservations.jsonl`. `loans.jsonl` keeps
its format. A refused command exits 1, like a refused `borrow`.
