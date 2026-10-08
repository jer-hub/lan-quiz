"""Phase 2: shuffle, kinds, teams, attempt scoring."""

import pytest
from pydantic import ValidationError

from app.game_manager import GameManager, QuestionData, normalize_short_answer
from app.schemas import QuestionCreate
from app.utils.shuffle import shuffle_options, unshuffle_index


def _mc():
    return QuestionData(id=1, text="Q", image=None, options=["A", "B", "C"], correct_indices=[0], time_limit=20)


async def test_shuffle_roundtrip():
    opts = ["A", "B", "C", "D"]
    shuffled, new_correct, order = shuffle_options(opts, [0], seed=42)
    assert sorted(shuffled) == sorted(opts)
    # Map back: shuffled position of canonical 0 scores correctly.
    remap = {old: new for new, old in enumerate(order)}
    assert new_correct == [remap[0]]
    assert unshuffle_index(remap[0], order) == 0


async def test_per_player_orders_differ_but_score():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_mc()])
    await m.join_game(s.pin, "s1", "Ada")
    await m.join_game(s.pin, "s2", "Bob")
    await m.start_game("h")
    sess, q = await m.advance_question("h")
    assert sess.option_map.get("s1") != sess.option_map.get("s2") or len(q.options) <= 2
    # Each player answers their own displayed correct position.
    for sid in ("s1", "s2"):
        order = sess.option_map[sid]
        displayed_correct = order.index(0)
        _, rec, _ = await m.submit_answer(sid, displayed_correct)
        assert rec.correct


async def test_question_kinds_validation():
    assert QuestionCreate(text="T?", options=["True", "False"], correct_indices=[0], kind="true_false")
    with pytest.raises(ValidationError):
        QuestionCreate(text="T?", options=["A", "B", "C"], correct_indices=[0], kind="true_false")
    assert QuestionCreate(text="Order", options=["A", "B"], correct_indices=[0, 1], kind="ordering")
    with pytest.raises(ValidationError):
        QuestionCreate(text="Order", options=["A", "B"], correct_indices=[0], kind="ordering")
    assert QuestionCreate(text="Capital?", kind="short_answer", answer_text="Paris")
    with pytest.raises(ValidationError):
        QuestionCreate(text="Capital?", kind="short_answer", answer_text="  ")


async def test_short_answer_scoring_normalized():
    assert normalize_short_answer("  PaRIS ") == "paris"
    m = GameManager()
    q = QuestionData(id=1, text="Cap?", image=None, options=[], correct_indices=[], time_limit=20, kind="short_answer", answer_text="Paris")
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[q])
    await m.join_game(s.pin, "s1", "Ada")
    await m.start_game("h")
    await m.advance_question("h")
    _, rec, _ = await m.submit_answer("s1", None, "paris ")
    assert rec.correct and rec.points > 0


async def test_team_mode_requires_team_and_scores():
    m = GameManager()
    s = await m.create_game(host_sid="h", quiz_id=1, quiz_title="T", questions=[_mc()], team_mode=True, teams=["Red", "Blue"])
    assert s.team_mode
    with pytest.raises(ValueError, match="Choose a team"):
        await m.join_game(s.pin, "s1", "Ada")
    with pytest.raises(ValueError, match="Unknown team"):
        await m.join_game(s.pin, "s1", "Ada", team="Green")
    await m.join_game(s.pin, "s1", "Ada", team="Red")
    await m.join_game(s.pin, "s2", "Bob", team="Blue")
    s.players["s1"].score = 1000
    s.players["s2"].score = 500
    teams = s.team_scores()
    assert teams[0]["team"] == "Red" and teams[0]["score"] == 1000


async def test_attempt_scoring_flat_base():
    from app.game_manager import normalize_short_answer as _n
    from app.models import Question as Q
    from app.routers.assignments import _score_attempt
    from app.schemas import AttemptAnswerIn
    from app.config import settings

    q1 = Q(text="2+2?", options_json='["3","4"]', correct_indices_json='[1]', time_limit=20, order_index=0, kind="mc")
    q2 = Q(text="Cap?", options_json='[]', correct_indices_json='[]', time_limit=20, order_index=1, kind="short_answer", answer_text="Paris")
    total, correct, _ = _score_attempt(
        [q1, q2],
        [AttemptAnswerIn(order_index=0, option_index=1), AttemptAnswerIn(order_index=1, answer_text="paris")],
        settings.score_base,
    )
    assert total == 2 * settings.score_base and correct == 2
