# lending

Read `README.md` first: the commands, the rules, the data files and the architecture.

## Conventions

- Branches: `feat/<slug>` for a feature.
- Commits: `<area>: <what changes>`, in the imperative, for example `loans: refuse an unknown member`.
- Standard library only, Python 3.11.
- The plan documents and everything committed are in English.

## Gate

One command checks the project:

    python3 -m unittest discover -s tests -q

There is no CI: run the gate before every commit.

## Critical zones

- The fine computation (`lending/fines.py`): the money members owe. A mistake there is charged to real people.
- The format of `loans.jsonl`: the fields of a loan line and their meaning. The accounting export of the library reads this file.
