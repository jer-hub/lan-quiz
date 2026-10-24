"""CSV for teachers to open in a spreadsheet, safe from formula injection."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

# A spreadsheet reads a cell starting with one of these as a formula.
FORMULA_SIGNS = ("=", "+", "-", "@")


def spreadsheet_safe(value: object) -> object:
    """A text cell starting with a formula sign gets a leading single quote, so it stays text."""
    if isinstance(value, str) and value.startswith(FORMULA_SIGNS):
        return "'" + value
    return value


def export_csv(rows: Iterable[Iterable[object]]) -> str:
    """Rows as CSV text, every text cell made spreadsheet-safe."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow([spreadsheet_safe(v) for v in row])
    return buf.getvalue()
