"""Snapshot roundtrip + restore pausing mid-question."""

from app.game_manager import GameManager, GameSession, GameStatus, QuestionData


def _q():
    return QuestionData(
        id=1, text="Q", image=None, options=["A", "B"], correct_indices=[0], time_limit=20
    )


async def test_snapshot_preserves_scores_and_roster():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()])
    await m.join_game(s.pin, "s1", "Ada")
    s.players["s1"].score = 750
    snap = s.to_snapshot()
    assert snap["pin"] == s.pin
    assert any(p["nickname"] == "Ada" and p["score"] == 750 for p in snap["players"])

    restored = GameSession.from_snapshot(snap)
    assert restored.pin == s.pin
    assert restored.quiz_id == 1
    names = {p.nickname: p.score for p in restored.players.values() if not p.is_host}
    assert names["Ada"] == 750


async def test_restore_pauses_mid_question():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_q(), _q()])
    await m.join_game(s.pin, "s1", "Ada")
    s.status = GameStatus.QUESTION
    s.current_question_index = 1
    snap = s.to_snapshot()
    restored = GameSession.from_snapshot(snap)
    # Timers cannot survive restart: pause for host to advance.
    assert restored.status == GameStatus.LEADERBOARD
    assert restored.current_question_index == 1


async def test_inject_restored_keeps_pin_without_live_sids():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()])
    await m.join_game(s.pin, "s1", "Ada")
    snap = s.to_snapshot()
    m2 = GameManager()
    restored = GameSession.from_snapshot(snap)
    m2.inject_restored(restored)
    assert m2.get_by_pin(s.pin) is not None
    assert m2.get_by_sid("s1") is None  # stale sid must reclaim
