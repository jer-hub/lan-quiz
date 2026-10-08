"""Lobby guards: 100-cap, nickname dedup, student single-session."""

import pytest

from app.game_manager import GameManager, QuestionData


def _q():
    return QuestionData(
        id=1, text="Q", image=None, options=["A", "B"], correct_indices=[0], time_limit=20
    )


async def _lobby(**kw):
    m = GameManager()
    s = await m.create_game(host_sid="host", quiz_id=1, quiz_title="T", questions=[_q()], **kw)
    return m, s


async def test_nickname_dedup_case_insensitive():
    m, s = await _lobby()
    await m.join_game(s.pin, "s1", "Ada")
    with pytest.raises(ValueError, match="already taken"):
        await m.join_game(s.pin, "s2", " ada ")


async def test_join_full_at_100():
    m, s = await _lobby()
    for i in range(100):
        await m.join_game(s.pin, f"s{i}", f"p{i}")
    with pytest.raises(ValueError, match="full"):
        await m.join_game(s.pin, "overflow", "extra")


async def test_student_code_single_session():
    m, s = await _lobby(assignment_id=7)
    await m.join_game(s.pin, "s1", "Ada", student_id=42)
    with pytest.raises(ValueError, match="already in the lobby"):
        await m.join_game(s.pin, "s2", "Bob", student_id=42)


async def test_assignment_requires_student_code():
    m, s = await _lobby(assignment_id=7)
    with pytest.raises(ValueError, match="student code"):
        await m.join_game(s.pin, "s1", "Ada")
