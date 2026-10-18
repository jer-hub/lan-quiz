"""Regression: ordering questions are graded on the full sequence, not on any single tap."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.game_manager import GameManager, QuestionData
from app.routers.assignments import _score_attempt
from app.schemas import AttemptAnswerIn

OPTIONS = ["first", "second", "third"]


def _ordering_question() -> QuestionData:
    return QuestionData(
        id=1,
        text="Put these in order",
        image=None,
        options=list(OPTIONS),
        correct_indices=[0, 1, 2],
        time_limit=20,
        kind="ordering",
    )


async def _started_session(gm: GameManager):
    session = await gm.create_game(
        host_sid="H", quiz_id=1, quiz_title="t", questions=[_ordering_question()]
    )
    await gm.join_game(session.pin, "P1", "alice")
    await gm.start_game("H")
    await gm.advance_question("H")
    return session


def _submit(order):
    gm = GameManager()

    async def run():
        await _started_session(gm)
        return await gm.submit_answer("P1", order=order)

    return asyncio.run(run())


def test_correct_sequence_scores():
    _, record, _ = _submit([0, 1, 2])
    assert record.correct is True
    assert record.points > 0


def test_wrong_sequence_scores_zero():
    _, record, _ = _submit([2, 0, 1])
    assert record.correct is False
    assert record.points == 0


def test_single_tap_without_sequence_is_rejected():
    # Previously any single tap was scored correct because correct_indices held every position.
    with pytest.raises(ValueError):
        _submit(None)


@pytest.mark.parametrize("bad", [[0, 0, 1], [0, 1], [0, 1, 2, 3], [0, 1, 5], []])
def test_non_permutation_is_rejected(bad):
    with pytest.raises(ValueError):
        _submit(bad)


def test_homework_ordering_uses_sequence():
    questions = [
        SimpleNamespace(
            kind="ordering",
            options_json=json.dumps(OPTIONS),
            correct_indices_json=json.dumps([0, 1, 2]),
            answer_text=None,
        )
    ]
    right = [AttemptAnswerIn(order_index=0, order=[0, 1, 2])]
    wrong = [AttemptAnswerIn(order_index=0, option_index=2)]  # single tap, no sequence
    assert _score_attempt(questions, right, 1000)[1] == 1
    assert _score_attempt(questions, wrong, 1000)[1] == 0
