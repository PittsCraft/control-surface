# Interview: export the shelf as CSV

## Questions

### Q1. How are fields quoted?

Options:
- A. The default of Python's `csv` module: quoted only when they hold a comma, a quote or a line
  break.
- B. Every field quoted.

Recommended: A, spreadsheets read both and A keeps the file readable.

Answer (2026-09-29): A.

### Q2. What does an empty shelf print?

Options:
- A. The header line alone.
- B. Nothing.

Recommended: A, the import expects the header.

Answer (2026-09-29): A, the header alone.

### Q3. Which columns does the export hold?

Options:
- A. The title, the author and the year.
- B. The title, the author, the year and the ISBN.

Recommended: A, a smaller file.

Answer (2026-09-29): A.

### Q4. In what format is a shelf file kept?

Options:
- A. JSON Lines, one book per line.
- B. One JSON array for the whole shelf.

Recommended: A.

Answer (2026-09-29): A, as it is today.

## Amendments

## Plan change decisions

## Instructions after a block

## Git
