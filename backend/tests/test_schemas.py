"""Schema validators: options count, correct_indices range, time_limit."""

import pytest
from pydantic import ValidationError

from app.schemas import AssignmentCreate, QuestionCreate


def _q(**kw):
    base = {
        "text": "2+2?",
        "options": ["3", "4"],
        "correct_indices": [1],
        "time_limit": 20,
    }
    base.update(kw)
    return QuestionCreate(**base)


def test_valid_question():
    q = _q()
    assert q.correct_indices == [1]


def test_rejects_single_option():
    with pytest.raises(ValidationError):
        _q(options=["only"])


def test_rejects_seven_options():
    with pytest.raises(ValidationError):
        _q(options=["a", "b", "c", "d", "e", "f", "g"], correct_indices=[0])


def test_rejects_empty_option():
    with pytest.raises(ValidationError):
        _q(options=["a", "   "])


def test_rejects_out_of_range_index():
    with pytest.raises(ValidationError):
        _q(correct_indices=[5])


def test_rejects_bad_time_limit():
    with pytest.raises(ValidationError):
        _q(time_limit=4)
    with pytest.raises(ValidationError):
        _q(time_limit=121)


def test_score_policy_validator():
    a = AssignmentCreate(class_id=1, quiz_id=1, score_policy="BEST")
    assert a.score_policy == "best"
    with pytest.raises(ValidationError):
        AssignmentCreate(class_id=1, quiz_id=1, score_policy="average")
