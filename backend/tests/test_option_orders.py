"""Regression: players in one game get different option orders whenever the question allows it.

Previously two players drew the same order about 1 time in 6 on a 3-option question,
because the code did not check for collisions and the test assumed it did.
"""

import asyncio

from app.game_manager import GameManager, QuestionData


def _question() -> QuestionData:
    return QuestionData(
        id=1, text="Q", image=None, options=["A", "B", "C"], correct_indices=[0], time_limit=20
    )


async def _orders_for_one_game() -> tuple[list[int], list[int]]:
    gm = GameManager()
    session = await gm.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_question()])
    await gm.join_game(session.pin, "s1", "Ada")
    await gm.join_game(session.pin, "s2", "Bob")
    await gm.start_game("h")
    sess, _ = await gm.advance_question("h")
    return sess.option_map["s1"], sess.option_map["s2"]


def test_two_players_never_share_an_order_across_many_games():
    async def run():
        return [await _orders_for_one_game() for _ in range(300)]

    results = asyncio.run(run())
    collisions = [pair for pair in results if pair[0] == pair[1]]
    assert collisions == []
