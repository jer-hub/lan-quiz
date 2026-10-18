"""Roster rules shared by the classes and auth routers."""

from __future__ import annotations

import csv
import io

STUDENT_PASSWORD_MIN = 6  # minimum length for a supplied student password
MAX_CSV_ROWS = 500  # data rows per roster or teacher CSV import

ROSTER_HEADERS = [
    "username",
    "password",
    "first_name",
    "last_name",
    "email",
    "school_id",
    "class_section",
]


def read_csv_rows(raw: str) -> list[dict[str, str]]:
    """Parse roster CSV text: exact header sequence and the row cap.

    Raises ValueError with the client-facing message when the file is rejected.
    """
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ValueError("Empty CSV")
    headers = [h.strip() if h else "" for h in reader.fieldnames]
    if headers != ROSTER_HEADERS:
        raise ValueError("CSV must have headers in order: " + ",".join(ROSTER_HEADERS))
    data_rows = list(reader)
    if len(data_rows) > MAX_CSV_ROWS:
        raise ValueError(f"CSV has more than {MAX_CSV_ROWS} data rows (max {MAX_CSV_ROWS})")
    return data_rows
