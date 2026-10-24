"""Live game answers count toward mastery (#15).

A live classroom game is driven through the server's registered socket handlers; the
mastery report is read through the HTTP API.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import socketio

from app import socket_handlers
from app.game_manager import GameStatus, game_manager
from app.socket_handlers import register_socket_handlers
from tests.test_mastery_report import Classroom, _question, client  # noqa: F401

HOST = "HOST-LIVE"


def _cell(report: dict, student_id: int, topic: str) -> dict:
    assert topic in report["topics"], f"{topic} not in report topics {report['topics']}"
    row = next(r for r in report["rows"] if r["student_id"] == student_id)
    return next(c for c in row["cells"] if c["topic"] == topic)


class _Recorder:
    """Stands in for socket I/O: keeps every emit with its target."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict, str | None]] = []

    async def emit(self, event, data=None, to=None, room=None, **kwargs):
        self.events.append((event, data or {}, to or room))
        await asyncio.sleep(0)

    async def enter_room(self, *args, **kwargs):
        return None

    async def leave_room(self, *args, **kwargs):
        return None

    def last(self, event: str, to: str | None = None) -> dict:
        found = [d for e, d, t in self.events if e == event and (to is None or t == to)]
        assert found, f"no {event} emitted to {to}: {[e for e, _, _ in self.events]}"
        return found[-1]


class LiveGame:
    """A live game hosted by the classroom's teacher, played through the socket handlers."""

    def __init__(self, room: Classroom, recorder: _Recorder, handlers: dict) -> None:
        self.room = room
        self.recorder = recorder
        self.handlers = handlers
        self.pin = ""

    @classmethod
    async def host(cls, room: Classroom, *, classroom: bool = True, teams: list[str] | None = None) -> "LiveGame":
        """Host the room's assignment as a classroom game, or (classroom=False) its quiz as an open game."""
        recorder = _Recorder()
        sio = socketio.AsyncServer(async_mode="asgi")
        sio.emit = recorder.emit  # type: ignore[assignment]
        sio.enter_room = recorder.enter_room  # type: ignore[assignment]
        sio.leave_room = recorder.leave_room  # type: ignore[assignment]
        register_socket_handlers(sio)
        game = cls(room, recorder, sio.handlers["/"])
        data: dict = {"token": room.teacher["Authorization"].removeprefix("Bearer ")}
        if classroom:
            data["assignment_id"] = room.assignment_id
        else:
            data["quiz_id"] = room.quiz["id"]
        if teams:
            data.update(team_mode=True, teams=teams)
        await game.handlers["create_game"](HOST, data)
        game.pin = recorder.last("game_created", HOST)["pin"]
        return game

    async def join(self, sid: str, *, code: str = "", nickname: str = "", team: str | None = None) -> None:
        payload = {"pin": self.pin, "nickname": nickname or code, "student_code": code}
        if team:
            payload["team"] = team
        await self.handlers["join_game"](sid, payload)
        assert self.recorder.last("joined", sid)["pin"] == self.pin

    async def start(self) -> None:
        await self.handlers["start_game"](HOST, {})

    async def answer(self, sid: str, right: bool) -> None:
        """Pick the right or wrong option as this player sees them (options are shuffled per player)."""
        options = self.recorder.last("question_started", sid)["options"]
        await self.handlers["submit_answer"](sid, {"option_index": options.index("right" if right else "wrong")})

    async def next(self) -> None:
        """Host continues: closes the open question if any, then moves on (the last move finishes the game)."""
        session = game_manager.get_by_pin(self.pin)
        if session is not None and session.status == GameStatus.QUESTION:
            await self.handlers["next_question"](HOST, {})
        await self.handlers["next_question"](HOST, {})

    async def play(self, rounds: list[dict[str, bool | None]]) -> None:
        """Start and play to the end. rounds[i] maps a player's sid to right/wrong, or None to leave it unanswered."""
        await self.start()
        for answers in rounds:
            for sid, right in answers.items():
                if right is not None:
                    await self.answer(sid, right)
            await self.next()
        assert game_manager.get_by_pin(self.pin) is None, "game should be finished"


@pytest.fixture(autouse=True)
def _sockets_use_test_db(monkeypatch):
    """Point the socket handlers at the test database the client fixture set up."""
    import app.database as database

    monkeypatch.setattr(socket_handlers, "AsyncSessionLocal", lambda: database.AsyncSessionLocal())


async def test_a_tagged_question_answered_in_a_finished_classroom_game_counts(client):
    room = await Classroom.create(client, "t_live", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 5)])
    ada = await room.add_student("Ada", "ADA01")
    game = await LiveGame.host(room)
    await game.join("ADA", code="ADA01")

    await game.play([{"ADA": True}, {"ADA": True}, {"ADA": False}, {"ADA": True}])

    fractions = _cell(await room.mastery_report(), ada["id"], "Fractions")
    assert (fractions["answer_count"], fractions["accuracy"]) == (4, 75)


async def test_a_guest_players_answers_do_not_count(client):
    room = await Classroom.create(client, "t_guest", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 4)])
    await room.add_student("Ada", "ADA01")
    # An open game of the class's quiz: anyone joins by nickname, even with a student's name.
    game = await LiveGame.host(room, classroom=False)
    await game.join("GUEST", nickname="Ada")

    await game.play([{"GUEST": True}, {"GUEST": True}, {"GUEST": True}])

    report = await room.mastery_report()
    assert report["topics"] == []
    assert report["untagged_answer_count"] == 0


async def test_team_mode_answers_count_for_each_student(client):
    room = await Classroom.create(client, "t_team", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 4)])
    ada = await room.add_student("Ada", "ADA01")
    bea = await room.add_student("Bea", "BEA01")
    cy = await room.add_student("Cy", "CY01")
    game = await LiveGame.host(room, teams=["Red", "Blue"])
    await game.join("ADA", code="ADA01", team="Red")
    await game.join("BEA", code="BEA01", team="Red")
    await game.join("CY", code="CY01", team="Blue")

    await game.play(
        [
            {"ADA": True, "BEA": False, "CY": True},
            {"ADA": True, "BEA": False, "CY": False},
            {"ADA": True, "BEA": True, "CY": False},
        ]
    )

    report = await room.mastery_report()
    assert _cell(report, ada["id"], "Fractions")["accuracy"] == 100
    assert _cell(report, bea["id"], "Fractions")["accuracy"] == pytest.approx(33.3)
    assert _cell(report, cy["id"], "Fractions")["accuracy"] == pytest.approx(33.3)


async def test_a_question_a_student_did_not_answer_adds_nothing(client):
    room = await Classroom.create(client, "t_skip", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 5)])
    ada = await room.add_student("Ada", "ADA01")
    bea = await room.add_student("Bea", "BEA01")
    game = await LiveGame.host(room)
    await game.join("ADA", code="ADA01")
    await game.join("BEA", code="BEA01")

    await game.play(
        [
            {"ADA": True, "BEA": True},
            {"ADA": True, "BEA": None},
            {"ADA": True, "BEA": True},
            {"ADA": None, "BEA": True},
        ]
    )

    report = await room.mastery_report()
    for student in (ada, bea):
        fractions = _cell(report, student["id"], "Fractions")
        assert (fractions["answer_count"], fractions["accuracy"]) == (3, 100)


async def test_live_and_homework_answers_on_a_topic_combine_in_one_accuracy(client):
    room = await Classroom.create(client, "t_both", [_question("Q1", ["Fractions"]), _question("Q2", ["Fractions"])])
    ada = await room.add_student("Ada", "ADA01")
    await room.submit_attempt(ada, [0, 1])  # homework: right, wrong
    game = await LiveGame.host(room)
    await game.join("ADA", code="ADA01")

    await game.play([{"ADA": True}, {"ADA": True}])

    fractions = _cell(await room.mastery_report(), ada["id"], "Fractions")
    assert (fractions["answer_count"], fractions["accuracy"]) == (4, 75)


async def test_a_live_answer_counts_as_given_when_its_question_ended_not_when_the_game_ended(client):
    room = await Classroom.create(client, "t_live_order", [_question("Q1", ["Fractions"]), _question("Q2", ["Fractions"])])
    ada = await room.add_student("Ada", "ADA01")
    game = await LiveGame.host(room)
    await game.join("ADA", code="ADA01")
    await game.start()
    await game.answer("ADA", False)  # live question 1: wrong; the last answer closes it

    # Between the two live questions, Ada submits ten right homework answers.
    for _ in range(5):
        await room.submit_attempt(ada, [0, 0])

    await game.handlers["next_question"](HOST, {})  # question 2
    await game.answer("ADA", True)
    await game.next()
    assert game_manager.get_by_pin(game.pin) is None

    # Most recent 10: live question 2 and nine homework answers. The early live mistake falls out.
    fractions = _cell(await room.mastery_report(), ada["id"], "Fractions")
    assert (fractions["answer_count"], fractions["accuracy"]) == (10, 100)


async def test_ending_the_game_while_a_question_is_open_keeps_that_questions_answers(client):
    room = await Classroom.create(client, "t_live_end", [_question("Q1", ["Fractions"]), _question("Q2", ["Fractions"])])
    ada = await room.add_student("Ada", "ADA01")
    await room.add_student("Bea", "BEA01")
    game = await LiveGame.host(room)
    await game.join("ADA", code="ADA01")
    await game.join("BEA", code="BEA01")
    await game.start()
    await game.answer("ADA", True)  # Bea has not answered, so question 1 stays open

    await game.handlers["end_game"](HOST, {})
    assert game_manager.get_by_pin(game.pin) is None

    fractions = _cell(await room.mastery_report(), ada["id"], "Fractions")
    assert (fractions["answer_count"], fractions["mastered"]) == (1, False)
    res = await client.get(f"/api/assignments/{room.assignment_id}/analysis", headers=room.teacher)
    assert res.status_code == 200, res.text
    [question_1] = res.json()["analysis"]
    assert (question_1["question_index"], question_1["total"], question_1["correct"]) == (0, 2, 1)


async def test_a_live_answer_records_the_topics_the_question_had_when_the_game_was_hosted(client):
    room = await Classroom.create(client, "t_retag_live", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 4)])
    ada = await room.add_student("Ada", "ADA01")
    game = await LiveGame.host(room)
    await game.join("ADA", code="ADA01")

    # The teacher re-tags the quiz while the game is in its lobby.
    questions = room.quiz["questions"]
    for q in questions:
        q["topics"] = ["Decimals"]
    res = await client.put(f"/api/quizzes/{room.quiz['id']}", json={"questions": questions}, headers=room.teacher)
    assert res.status_code == 200, res.text

    await game.play([{"ADA": True}, {"ADA": True}, {"ADA": True}])

    report = await room.mastery_report()
    assert report["topics"] == ["Fractions"]
    assert _cell(report, ada["id"], "Fractions")["answer_count"] == 3


async def test_a_game_restored_after_a_restart_records_every_answer_with_its_topics(client):
    from app.game_manager import GameSession
    from app.session_store import load_snapshots

    room = await Classroom.create(client, "t_restore", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 4)])
    ada = await room.add_student("Ada", "ADA01")
    game = await LiveGame.host(room)
    await game.join("ADA", code="ADA01")
    await game.start()
    await game.answer("ADA", True)
    await game.next()  # reveal of question 1 is saved to the snapshot; question 2 starts
    await game.answer("ADA", True)  # the last answer closes question 2; the game waits on its leaderboard

    # The server restarts: the in-memory game is lost and comes back from its snapshot, as at startup.
    snapshot = next(s for s in await load_snapshots() if s["pin"] == game.pin)
    await game_manager.cleanup_game(game.pin)
    game_manager.inject_restored(GameSession.from_snapshot(snapshot))

    # The host reclaims the game and Ada rejoins on a new connection.
    token = room.teacher["Authorization"].removeprefix("Bearer ")
    await game.handlers["reclaim_game"](HOST, {"token": token, "pin": game.pin})
    await game.join("ADA-2", code="ADA01")
    await game.handlers["next_question"](HOST, {})  # question 3
    await game.answer("ADA-2", False)
    await game.next()
    assert game_manager.get_by_pin(game.pin) is None

    fractions = _cell(await room.mastery_report(), ada["id"], "Fractions")
    assert (fractions["answer_count"], fractions["accuracy"]) == (3, pytest.approx(66.7))
