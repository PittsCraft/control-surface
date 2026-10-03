Add an `overdue` command, so the desk can see which loans are late.

`python3 -m lending overdue` prints one line per open loan past its due date as of today:
`<book> <member> <due> <days late>`, the most days late first. It takes no argument.
