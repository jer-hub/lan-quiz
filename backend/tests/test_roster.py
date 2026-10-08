"""Roster CSV: exact header order, username->code, first+last->name."""

import pytest

from app.routers.classes import ROSTER_HEADERS, parse_roster_csv


def test_headers_constant():
    assert ROSTER_HEADERS == [
        "username", "password", "first_name", "last_name",
        "email", "school_id", "class_section",
    ]


def test_valid_mapping():
    raw = (
        "username,password,first_name,last_name,email,school_id,class_section\n"
        "ada01,,Ada,Lovelace,ada@school.edu,S1001,7-A\n"
        "bob02,secret42,Bob,Nguyen,bob@school.edu,S1002,7-A\n"
    )
    rows, skipped = parse_roster_csv(raw)
    assert skipped == []
    assert rows[0]["student_code"] == "ADA01"
    assert rows[0]["display_name"] == "Ada Lovelace"
    assert rows[0]["password"] == "ADA01"  # blank defaults to username
    assert rows[1]["password"] == "secret42"


def test_wrong_order_rejected():
    raw = "password,username,first_name,last_name,email,school_id,class_section\nx,y,A,B,e,S,7-A\n"
    with pytest.raises(ValueError, match="must have headers in order"):
        parse_roster_csv(raw)


def test_missing_name_skipped_with_row_number():
    raw = (
        "username,password,first_name,last_name,email,school_id,class_section\n"
        ",,,Nobody,e,S,7-A\n"
    )
    rows, skipped = parse_roster_csv(raw)
    assert rows == []
    assert skipped == [{"row": 2, "reason": "missing username or name"}]
