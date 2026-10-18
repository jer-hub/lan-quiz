"""Student password rules: roster import and add-student share one standard.

A supplied password needs at least 6 characters. An omitted password gets a
generated one (at least 8 characters, never the student code) that is returned
once in the response and works for login.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import hash_password, teacher_token
from app.database import Base, get_db
from app.main import fastapi_app
from app.models import ClassRoom, User

ROSTER_HEADER = "username,password,first_name,last_name,email,school_id,class_section\n"


@pytest.fixture()
async def env(tmp_path) -> AsyncIterator[dict[str, Any]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    async with Session() as session:
        teacher = User(
            username="mrs.lee", password_hash=hash_password("teacherpass"), role="teacher"
        )
        session.add(teacher)
        await session.flush()
        classroom = ClassRoom(teacher_id=teacher.id, name="Period 1", join_code="PERIOD")
        session.add(classroom)
        await session.commit()
        token = teacher_token(teacher)
        class_id = classroom.id

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "headers": {"Authorization": f"Bearer {token}"},
            "class_id": class_id,
        }
    fastapi_app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client: httpx.AsyncClient, code: str, password: str) -> httpx.Response:
    return await client.post(
        "/api/auth/student/login",
        json={"student_code": code, "password": password, "join_code": "PERIOD"},
    )


async def test_add_student_short_password_refused(env):
    c, cid = env["client"], env["class_id"]
    res = await c.post(
        f"/api/classes/{cid}/students",
        headers=env["headers"],
        json={"display_name": "Ada", "student_code": "ada01", "password": "abc12"},
    )
    assert res.status_code in (400, 422)
    assert (await _login(c, "ADA01", "abc12")).status_code == 401


async def test_add_student_without_password_gets_generated_password(env):
    c, cid = env["client"], env["class_id"]
    res = await c.post(
        f"/api/classes/{cid}/students",
        headers=env["headers"],
        json={"display_name": "Ada Lovelace", "student_code": "ada01"},
    )
    assert res.status_code == 201
    generated = res.json()["generated_password"]
    assert len(generated) >= 8
    assert generated != "ADA01"
    assert (await _login(c, "ADA01", "ADA01")).status_code == 401
    assert (await _login(c, "ADA01", generated)).status_code == 200


async def test_generated_password_is_returned_once(env):
    c, cid = env["client"], env["class_id"]
    await c.post(
        f"/api/classes/{cid}/students",
        headers=env["headers"],
        json={"display_name": "Ada", "student_code": "ada01"},
    )
    listed = await c.get(f"/api/classes/{cid}/students", headers=env["headers"])
    assert listed.status_code == 200
    assert "generated_password" not in listed.json()[0]


async def test_roster_import_generates_password_for_blank_rows(env):
    c, cid = env["client"], env["class_id"]
    raw = (
        ROSTER_HEADER
        + "ada01,,Ada,Lovelace,,,\n"
        + "bob02,secret42,Bob,Nguyen,,,\n"
        + "cyz03,abc,Cy,Zed,,,\n"
    )
    res = await c.post(
        f"/api/classes/{cid}/students/import",
        headers=env["headers"],
        files={"file": ("roster.csv", raw.encode(), "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()
    added = {s["student_code"]: s for s in body["added"]}
    assert set(added) == {"ADA01", "BOB02"}
    assert body["skipped"] == [{"row": 4, "reason": "password too short (min 6)"}]

    ada_pw = added["ADA01"]["generated_password"]
    assert len(ada_pw) >= 8
    assert ada_pw != "ADA01"
    assert (await _login(c, "ADA01", "ADA01")).status_code == 401
    assert (await _login(c, "ADA01", ada_pw)).status_code == 200

    assert added["BOB02"].get("generated_password") is None
    assert (await _login(c, "BOB02", "secret42")).status_code == 200
