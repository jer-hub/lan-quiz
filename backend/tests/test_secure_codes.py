"""Join codes and game PINs come from a cryptographically secure source.

These tests assert the generator's source (secrets.choice is used, and the
non-cryptographic random.choices is never called), then check that the
shape is unchanged: 6 characters from the unambiguous alphabet.
"""

import random
import secrets

import pytest

from app.game_manager import GameManager, QuestionData
from app.routers import classes

# A-Z and 2-9 with I, O removed: the same unambiguous alphabet as before.
ALPHABET = set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


@pytest.fixture
def secure_source_spy(monkeypatch):
    calls: list = []
    real_choice = secrets.choice

    def spy(seq):
        calls.append(seq)
        return real_choice(seq)

    def forbidden(*args, **kwargs):
        raise AssertionError("non-cryptographic random.choices was used")

    monkeypatch.setattr(secrets, "choice", spy)
    monkeypatch.setattr(random, "choices", forbidden)
    return calls


def _q():
    return QuestionData(
        id=1, text="Q", image=None, options=["A", "B"], correct_indices=[0], time_limit=20
    )


async def test_game_pin_drawn_from_secure_source(secure_source_spy):
    m = GameManager()
    s = await m.create_game(host_sid="host", quiz_id=1, quiz_title="T", questions=[_q()])
    assert secure_source_spy, "game PIN was not drawn from secrets"
    assert len(s.pin) == 6
    assert set(s.pin) <= ALPHABET


def test_class_join_code_drawn_from_secure_source(secure_source_spy):
    code = classes._gen_join_code()
    assert secure_source_spy, "class join code was not drawn from secrets"
    assert len(code) == 6
    assert set(code) <= ALPHABET
