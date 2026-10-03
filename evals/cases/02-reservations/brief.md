# Brief: the reservations

What I know about this need and did not write in it.

## Rules

Reserving:

- Only a book that is out can be reserved: a book on loan, or a book held for another member,
  behind whom the new member queues. A book that sits free on the shelf cannot be reserved: the
  `reserve` is refused, the member just borrows it.
- An unknown book or an unknown member is refused.
- A member cannot reserve the same book twice: the second `reserve` is refused while the first
  reservation stands.
- A member cannot reserve a book they have on loan: refused.
- The queue of a book follows the order of the reservations. No priority for staff, no limit on
  the number of reservations.

Cancelling:

- `cancel` of a reservation that does not exist is refused.
- Cancelling a reservation that is still waiting just removes it: the others move up.
- Cancelling a reservation whose book is held passes the hold to the next member of the queue at
  once: a new `hold` notice, and a new hold that starts that day. With nobody else in the queue,
  the book is free on the shelf again.

Holding:

- A hold starts the day the book is returned, or the day it is passed on by `cancel` or `expire`.
- The `hold` notice: `to` is the member, `kind` is `hold`, `on` is the day the hold starts. Its
  text names the book id and the last day to pick the book up.
- While a book is held, a `borrow` by anyone else is refused: the other members of the queue as
  well as members who never reserved.
- The holder picks the book up with the ordinary `borrow`. The loan is an ordinary loan, 14 days
  from that day, with the same printed line, and their reservation is over. The rest of the
  queue stays and waits for the next return.
- A return with nobody in the queue changes nothing: no notice, the book is free. `return`
  prints the same line as today in every case.

Expiring:

- The length of a hold is the number of days the need gives. A hold that starts on day D and
  lasts N days can be picked up through day D+N. `expire` run on day D+N+1 or later drops it;
  run on day D+N or before, it leaves it alone.
- `expire` is the only thing that ends a hold nobody picked up: `borrow` does not look at the
  age of a hold. The library runs `expire` every morning.
- A dropped hold is a reservation that is over: the member is out of the queue and must reserve
  again. They get no notice about it.
- The hold then passes to the next member of the queue: a new `hold` notice, and a hold of the
  full length that starts the day `expire` runs. With nobody else, the book is free on the shelf.
- `expire` takes no argument, handles every book, and exits 0 also when there is nothing to drop.

Files:

- Nothing is added to a loan line: `loans.jsonl` keeps its five fields and their meaning.
- The length of a hold is fixed in the code.

## Not mine to decide

- The fields of a line of `reservations.jsonl`.
- What `reserve`, `cancel` and `expire` print: I only rely on their exit codes.
- The wording of the notice and of the refusals.
- Which module holds the reservations, and the names of the functions.
- How the tests are laid out.
