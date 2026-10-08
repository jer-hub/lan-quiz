"""Gradebook policy: best picks max score, latest picks max played_at."""

from datetime import datetime, timezone

from app.routers.assignments import _pick_score


def _dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_best_picks_max_score():
    plays = [(100, 2, _dt(1)), (900, 1, _dt(2)), (500, 3, _dt(3))]
    assert _pick_score(plays, "best")[0] == 900


def test_latest_picks_newest():
    plays = [(900, 1, _dt(1)), (100, 2, _dt(3))]
    picked = _pick_score(plays, "latest")
    assert picked[0] == 100


def test_empty_returns_none():
    assert _pick_score([], "best") is None
    assert _pick_score([], "latest") is None
