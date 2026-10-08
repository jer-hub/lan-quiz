"""Teacher CSV import validation."""

import pytest

from app.routers.auth import validate_teacher_import_row


def test_valid_row():
    assert validate_teacher_import_row("JSmith", "secret99") == ("jsmith", "secret99")


def test_blank_password_defaults_to_username():
    assert validate_teacher_import_row("janesmith", "") == ("janesmith", "janesmith")


def test_short_username_rejected():
    with pytest.raises(ValueError, match="min 3"):
        validate_teacher_import_row("ab", "secret99")


def test_short_password_rejected():
    with pytest.raises(ValueError, match="min 6"):
        validate_teacher_import_row("bobdoe", "123")
    # blank password defaulting to a short username is also rejected
    with pytest.raises(ValueError, match="min 6"):
        validate_teacher_import_row("bob", "")
