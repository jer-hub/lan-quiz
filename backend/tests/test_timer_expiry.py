"""Regression: a question that expires on its timer must finish its reveal tail.

Previously the timer task cancelled itself inside end_question, so after the
question_ended emit the leaderboard_update and snapshot save were skipped.
"""

from __future__ import annotations

import asyncio

import socketio

from app import socket_handlers
from app.game_manager import QuestionData, game_manager
from app.socket_handlers import register_socket_handlers


class _Recorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def emit(self, event, data=None, **kwargs):
        self.events.append(event)
        # Yield like real socket I/O does, so any pending cancel would land here.
        await asyncio.sleep(0)

    async def enter_room(self, *args, **kwargs):
        return None

    async def leave_room(self, *args, **kwargs):
        return None


def test_expiring_question_emits_full_reveal_tail(monkeypatch):
    recorder = _Recorder()
    saved: list[str] = []

    async def fake_save_snapshot(session):
        await asyncio.sleep(0)
        saved.append(session.pin)

    monkeypatch.setattr(socket_handlers, "save_snapshot", fake_save_snapshot)

    sio = socketio.AsyncServer(async_mode="asgi")
    sio.emit = recorder.emit  # type: ignore[assignment]
    sio.enter_room = recorder.enter_room  # type: ignore[assignment]
    register_socket_handlers(sio)
    start_game = sio.handlers["/"]["start_game"]

    async def run():
        question = QuestionData(
            id=1,
            text="Quick",
            image=None,
            options=["a", "b"],
            correct_indices=[0],
            time_limit=1,
        )
        session = await game_manager.create_game(
            host_sid="HOST-TIMER", quiz_id=1, quiz_title="t", questions=[question]
        )
        try:
            await game_manager.join_game(session.pin, "PLAYER-TIMER", "bob")
            await start_game("HOST-TIMER", {})
            # Nobody answers; the 1s timer must expire and finalize the question.
            await asyncio.sleep(1.5)
        finally:
            await game_manager.cleanup_game(session.pin)
        return session.pin

    pin = asyncio.run(run())

    assert "question_ended" in recorder.events
    assert "leaderboard_update" in recorder.events, recorder.events
    assert recorder.events.index("leaderboard_update") > recorder.events.index("question_ended")
    assert pin in saved
