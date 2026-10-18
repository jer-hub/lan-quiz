"""Class password enforcement on join (#8).

When a class has require_password on, a classroom game join needs the student's
password. A wrong or missing password gets the same error as an unknown code, and
a reconnect (rejoin_sid) is checked the same way. With the setting off, joins
behave as before.
"""

from __future__ import annotations

import asyncio

import socketio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import httpx

from app import database, socket_handlers
from app.auth import hash_password
from app.database import Base
from app.game_manager import QuestionData, game_manager
from app.models import ClassRoom, Student, User
from app.socket_handlers import register_socket_handlers

PASSWORD = "pw-secret-1"
UNKNOWN_CODE_ERROR = "Student code not found in this class roster."


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event, data=None, **kwargs):
        self.events.append((event, data or {}))
        await asyncio.sleep(0)

    async def enter_room(self, *args, **kwargs):
        return None

    async def leave_room(self, *args, **kwargs):
        return None

    def errors(self) -> list[str]:
        return [d["message"] for e, d in self.events if e == "error"]

    def joined(self) -> list[dict]:
        return [d for e, d in self.events if e == "joined"]


def _question() -> QuestionData:
    return QuestionData(
        id=1, text="Q", image=None, options=["A", "B"], correct_indices=[0], time_limit=20
    )


def _run_join_scenario(tmp_path, monkeypatch, require_password: bool, scenario):
    """Build a class with one student, start a classroom game, run scenario(handlers, pin, recorder)."""
    monkeypatch.setattr(socket_handlers, "save_snapshot", _no_snapshot)

    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'join.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_local() as db:
            teacher = User(username="mrs.lee", password_hash=hash_password("teacherpass"), role="teacher")
            db.add(teacher)
            await db.flush()
            classroom = ClassRoom(
                teacher_id=teacher.id,
                name="Period 1",
                join_code="PERIOD",
                require_password=require_password,
            )
            db.add(classroom)
            await db.flush()
            db.add(
                Student(
                    class_id=classroom.id,
                    display_name="Ada",
                    student_code="ADA01",
                    password_hash=hash_password(PASSWORD),
                )
            )
            await db.commit()
            class_id = classroom.id

        monkeypatch.setattr(socket_handlers, "AsyncSessionLocal", session_local)
        monkeypatch.setattr(database, "AsyncSessionLocal", session_local)

        recorder = _Recorder()
        sio = socketio.AsyncServer(async_mode="asgi")
        sio.emit = recorder.emit  # type: ignore[assignment]
        sio.enter_room = recorder.enter_room  # type: ignore[assignment]
        register_socket_handlers(sio)
        handlers = sio.handlers["/"]

        session = await game_manager.create_game(
            host_sid="HOST-JOIN",
            quiz_id=1,
            quiz_title="t",
            questions=[_question()],
            class_id=class_id,
            assignment_id=9,
        )
        try:
            return await scenario(handlers, session.pin, recorder)
        finally:
            await game_manager.cleanup_game(session.pin)
            await engine.dispose()

    return asyncio.run(run())


async def _no_snapshot(session):
    return None


def test_pin_peek_tells_the_join_screen_a_password_is_required(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        from app.main import fastapi_app

        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/games/pin/{pin}")
        assert res.status_code == 200, res.text
        return res.json()

    info = _run_join_scenario(tmp_path, monkeypatch, require_password=True, scenario=scenario)
    assert info["requires_student_code"] is True
    assert info["requires_password"] is True


def test_pin_peek_reports_no_password_when_setting_off(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        from app.main import fastapi_app

        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/games/pin/{pin}")
        return res.json()

    info = _run_join_scenario(tmp_path, monkeypatch, require_password=False, scenario=scenario)
    assert info["requires_password"] is False


def test_join_without_password_refused_when_setting_on(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        await handlers["join_game"]("P-NOPW", {"pin": pin, "nickname": "Ada", "student_code": "ADA01"})
        return rec

    rec = _run_join_scenario(tmp_path, monkeypatch, require_password=True, scenario=scenario)

    assert rec.joined() == []
    assert rec.errors(), "a join without the password must be refused"


def test_wrong_password_gets_same_error_as_unknown_code(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        await handlers["join_game"](
            "P-WRONG", {"pin": pin, "nickname": "Ada", "student_code": "ADA01", "password": "nope-nope"}
        )
        await handlers["join_game"](
            "P-UNKNOWN", {"pin": pin, "nickname": "Zed", "student_code": "ZZZ99", "password": PASSWORD}
        )
        return rec

    rec = _run_join_scenario(tmp_path, monkeypatch, require_password=True, scenario=scenario)

    assert rec.joined() == []
    assert rec.errors() == [UNKNOWN_CODE_ERROR, UNKNOWN_CODE_ERROR]


def test_correct_password_joins_when_setting_on(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        await handlers["join_game"](
            "P-OK", {"pin": pin, "nickname": "Ada", "student_code": "ADA01", "password": PASSWORD}
        )
        return rec

    rec = _run_join_scenario(tmp_path, monkeypatch, require_password=True, scenario=scenario)

    assert rec.errors() == []
    assert [j["sid"] for j in rec.joined()] == ["P-OK"]


def test_setting_off_join_without_password_still_works(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        await handlers["join_game"]("P-OFF", {"pin": pin, "nickname": "Ada", "student_code": "ADA01"})
        return rec

    rec = _run_join_scenario(tmp_path, monkeypatch, require_password=False, scenario=scenario)

    assert rec.errors() == []
    assert [j["sid"] for j in rec.joined()] == ["P-OFF"]


def test_reconnect_with_correct_password_is_accepted(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        await handlers["join_game"](
            "P-FIRST", {"pin": pin, "nickname": "Ada", "student_code": "ADA01", "password": PASSWORD}
        )
        await game_manager.mark_disconnected("P-FIRST")
        await handlers["join_game"](
            "P-AGAIN",
            {
                "pin": pin,
                "nickname": "Ada",
                "student_code": "ADA01",
                "password": PASSWORD,
                "rejoin_sid": "P-FIRST",
            },
        )
        return rec

    rec = _run_join_scenario(tmp_path, monkeypatch, require_password=True, scenario=scenario)

    assert rec.errors() == []
    assert [j["sid"] for j in rec.joined()] == ["P-FIRST", "P-AGAIN"]


def test_reconnect_with_wrong_password_is_refused(tmp_path, monkeypatch):
    async def scenario(handlers, pin, rec):
        await handlers["join_game"](
            "P-FIRST", {"pin": pin, "nickname": "Ada", "student_code": "ADA01", "password": PASSWORD}
        )
        await game_manager.mark_disconnected("P-FIRST")
        await handlers["join_game"](
            "P-AGAIN",
            {
                "pin": pin,
                "nickname": "Ada",
                "student_code": "ADA01",
                "password": "wrong-pass",
                "rejoin_sid": "P-FIRST",
            },
        )
        return rec

    rec = _run_join_scenario(tmp_path, monkeypatch, require_password=True, scenario=scenario)

    assert rec.errors() == [UNKNOWN_CODE_ERROR]
    assert [j["sid"] for j in rec.joined()] == ["P-FIRST"]
