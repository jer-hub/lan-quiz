"""Rejoin grace: disconnect keeps slot 60s, reclaim preserves score."""

import pytest

from app.game_manager import GameManager, QuestionData


def _q():
    return QuestionData(
        id=1, text="Q", image=None, options=["A", "B"], correct_indices=[0], time_limit=20
    )


async def test_disconnect_keeps_slot_then_rejoin_reclaims_score():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()])
    await m.join_game(s.pin, "s1", "Ada")
    s.players["s1"].score = 500

    await m.mark_disconnected("s1")
    assert s.players["s1"].connected is False
    # Same nickname auto-reclaims the disconnected slot (no duplicate).
    s2 = await m.join_game(s.pin, "s2", "Ada")
    assert s2.players["s2"].score == 500
    assert "s1" not in s2.players


async def test_explicit_rejoin_sid_reclaims():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()])
    await m.join_game(s.pin, "s1", "Ada")
    s.players["s1"].score = 500
    await m.mark_disconnected("s1")

    s2 = await m.join_game(s.pin, "s9", "Ada", rejoin_sid="s1")
    assert s2.players["s9"].score == 500
    assert "s1" not in s2.players


async def test_student_code_reclaims_without_rejoin_sid():
    m = GameManager()
    s = await m.create_game(
        host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()], assignment_id=9
    )
    await m.join_game(s.pin, "s1", "Ada", student_id=42)
    s.players["s1"].score = 300
    await m.mark_disconnected("s1")

    s2 = await m.join_game(s.pin, "s9", "Anything", student_id=42)
    assert s2.players["s9"].score == 300
    assert s2.players["s9"].nickname == "Ada"


async def test_connected_duplicate_still_blocked():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()])
    await m.join_game(s.pin, "s1", "Ada")
    with pytest.raises(ValueError, match="already taken"):
        await m.join_game(s.pin, "s2", "ada")


async def test_host_reclaim():
    m = GameManager()
    s = await m.create_game(
        host_sid="old-host", quiz_id=1, quiz_title="T", questions=[_q()], teacher_id=7
    )
    await m.mark_disconnected("old-host")
    s2 = await m.reclaim_host(s.pin, "new-host", 7)
    assert s2.host_sid == "new-host"
    assert "new-host" in s2.players


async def test_host_reclaim_wrong_teacher_blocked():
    m = GameManager()
    s = await m.create_game(
        host_sid="old-host", quiz_id=1, quiz_title="T", questions=[_q()], teacher_id=7
    )
    with pytest.raises(ValueError, match="hosting teacher"):
        await m.reclaim_host(s.pin, "intruder", 8)
