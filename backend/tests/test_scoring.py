"""Scoring bounds: correct fast=BASE, slow=BASE//2, wrong=0."""

from app.config import settings
from app.game_manager import calculate_score


def test_wrong_scores_zero():
    assert calculate_score(0, 20, False) == 0
    assert calculate_score(100, 20, False) == 0


def test_fast_correct_scores_base():
    base = settings.score_base
    assert calculate_score(0, 20, True) == base


def test_slow_correct_clamped_to_half():
    base = settings.score_base
    assert calculate_score(20_000, 20, True) == base // 2
    assert calculate_score(99_000, 20, True) == base // 2


def test_midpoint_scales():
    base = settings.score_base
    mid = calculate_score(10_000, 20, True)
    assert base // 2 < mid < base
