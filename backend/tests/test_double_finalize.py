"""Regression: finalizing a question twice must not duplicate its history or reveal."""

from __future__ import annotations

import asyncio

from app.game_manager import GameManager, QuestionData


def _question() -> QuestionData:
    return QuestionData(
        id=1,
        text="Pick a",
        image=None,
        options=["a", "b"],
        correct_indices=[0],
        time_limit=20,
    )


def test_second_end_question_is_a_no_op():
    gm = GameManager()

    async def run():
        session = await gm.create_game(
            host_sid="H", quiz_id=1, quiz_title="t", questions=[_question()]
        )
        await gm.join_game(session.pin, "P1", "alice")
        await gm.start_game("H")
        await gm.advance_question("H")
        await gm.submit_answer("P1", 0)

        first = await gm.end_question(session)
        second = await gm.end_question(session)
        return session, first, second

    session, first, second = asyncio.run(run())

    assert first is not None
    assert second is None
    assert len(session.question_history) == 1
    assert session.status.value == "reveal"


def test_end_question_after_finish_does_not_reopen_reveal():
    gm = GameManager()

    async def run():
        session = await gm.create_game(
            host_sid="H", quiz_id=1, quiz_title="t", questions=[_question()]
        )
        await gm.join_game(session.pin, "P1", "alice")
        await gm.start_game("H")
        await gm.advance_question("H")
        await gm.end_question(session)
        await gm.set_leaderboard_status(session)
        again = await gm.end_question(session)
        return session, again

    session, again = asyncio.run(run())

    assert again is None
    assert session.status.value == "leaderboard"
    assert len(session.question_history) == 1
