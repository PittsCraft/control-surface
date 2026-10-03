Add a `remind` command that reminds the members who keep books past their due date.

`python3 -m lending remind` sends each member who has overdue loans one notice: a line in the
outbox with `kind` `reminder`, whose text names each overdue book id and the total fine owed as
of today, with two decimals. It prints one line per member reminded:
`<member> <number of loans> <total fine>`.

The fine is the existing computation, unchanged. No member is reminded twice on the same day.
