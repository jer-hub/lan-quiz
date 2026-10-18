"""Regression: changing a student's password follows the same 6-character minimum."""

import pytest
from pydantic import ValidationError

from app.schemas import StudentUpdate


def test_short_student_password_update_refused():
    with pytest.raises(ValidationError):
        StudentUpdate(password="abc")


def test_six_character_student_password_update_accepted():
    assert StudentUpdate(password="abcdef").password == "abcdef"
