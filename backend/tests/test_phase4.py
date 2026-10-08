"""Phase 4: peek exposes teams, health exposes loopback flag."""

from app.game_manager import GameManager, QuestionData
from app.routers import games


def _q():
    return QuestionData(id=1, text="Q", image=None, options=["A", "B"], correct_indices=[0], time_limit=20)


async def test_peek_includes_teams(monkeypatch):
    m = GameManager()
    s = await m.create_game(
        host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()],
        team_mode=True, teams=["Red", "Blue"],
    )
    monkeypatch.setattr(games, "game_manager", m)
    out = await games.peek_pin(s.pin)
    assert out["team_mode"] is True
    assert out["teams"] == ["Red", "Blue"]


async def test_peek_casual_no_teams(monkeypatch):
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_q()])
    monkeypatch.setattr(games, "game_manager", m)
    out = await games.peek_pin(s.pin)
    assert out["team_mode"] is False
    assert out["teams"] == []
