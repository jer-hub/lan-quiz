"""Class password setting (#7): migration adds it off by default; teachers toggle it via the class API."""

import sqlite3
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND = Path(__file__).resolve().parents[1]


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def _columns(db_path: Path, table: str) -> dict[str, dict]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        conn.close()
    return {r[1]: {"default": r[4], "notnull": r[3]} for r in rows}


def test_migration_chain_is_linear_with_single_head():
    heads = ScriptDirectory.from_config(_alembic_cfg()).get_heads()
    assert heads == ["0007_question_topics"]


def test_existing_classes_keep_working_with_password_setting_off(tmp_path, monkeypatch):
    db_path = tmp_path / "migrate.db"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_path}")

    # Build the schema as it was before this ticket, then add a class the way a v1.4 install has one.
    command.upgrade(_alembic_cfg(), "0005_history_questions")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) "
        "VALUES (1, 'teacher1', 'x', 'teacher', '2026-01-01 00:00:00')"
    )
    conn.execute(
        "INSERT INTO classes (id, teacher_id, name, join_code, created_at) "
        "VALUES (1, 1, 'Old class', 'ABCDEF', '2026-01-01 00:00:00')"
    )
    conn.commit()
    conn.close()

    command.upgrade(_alembic_cfg(), "head")

    assert "require_password" in _columns(db_path, "classes")
    conn = sqlite3.connect(db_path)
    value = conn.execute("SELECT require_password FROM classes WHERE id = 1").fetchone()[0]
    conn.close()
    assert value == 0


@pytest.fixture
async def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    command.upgrade(_alembic_cfg(), "head")

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    import app.database as database

    monkeypatch.setattr(database, "AsyncSessionLocal", session_local)

    from app.main import fastapi_app

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _teacher(client: httpx.AsyncClient, username: str) -> dict[str, str]:
    # Teacher self-registration closes after the first account, so insert the row directly.
    import app.database as database
    from app.auth import hash_password
    from app.models import User

    async with database.AsyncSessionLocal() as session:
        session.add(User(username=username, password_hash=hash_password("secret123"), role="teacher"))
        await session.commit()
    res = await client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


async def test_new_class_defaults_to_password_off(client):
    headers = await _teacher(client, "teacher_default")
    res = await client.post("/api/classes", json={"name": "Period 1"}, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["require_password"] is False


async def test_teacher_turns_setting_on_and_off(client):
    headers = await _teacher(client, "teacher_toggle")
    cls = (await client.post("/api/classes", json={"name": "Period 2"}, headers=headers)).json()
    url = f"/api/classes/{cls['id']}"

    res = await client.put(url, json={"require_password": True}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["require_password"] is True
    assert (await client.get(url, headers=headers)).json()["require_password"] is True

    res = await client.put(url, json={"require_password": False}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["require_password"] is False


async def test_rename_leaves_password_setting_alone(client):
    headers = await _teacher(client, "teacher_rename")
    cls = (await client.post("/api/classes", json={"name": "Period 3"}, headers=headers)).json()
    url = f"/api/classes/{cls['id']}"
    await client.put(url, json={"require_password": True}, headers=headers)

    res = await client.put(url, json={"name": "Period 3 renamed"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Period 3 renamed"
    assert res.json()["require_password"] is True


async def test_update_with_no_fields_is_rejected(client):
    headers = await _teacher(client, "teacher_empty")
    cls = (await client.post("/api/classes", json={"name": "Period 4"}, headers=headers)).json()
    res = await client.put(f"/api/classes/{cls['id']}", json={}, headers=headers)
    assert res.status_code == 422


async def test_other_teacher_cannot_toggle(client):
    owner = await _teacher(client, "teacher_owner")
    other = await _teacher(client, "teacher_other")
    cls = (await client.post("/api/classes", json={"name": "Period 5"}, headers=owner)).json()
    res = await client.put(f"/api/classes/{cls['id']}", json={"require_password": True}, headers=other)
    assert res.status_code == 404
