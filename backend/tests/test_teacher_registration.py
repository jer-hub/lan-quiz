"""Teacher self-registration closes after the first teacher account.

Regression for issue #2: public POST /api/auth/register must refuse once a
teacher exists, unless ALLOW_TEACHER_REGISTRATION is enabled.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.routers import auth


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allow_teacher_registration", False)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await engine.dispose()


def _payload(username: str) -> dict:
    return {"username": username, "password": "secret99"}


async def test_first_registration_succeeds(client):
    resp = await client.post("/api/auth/register", json=_payload("firstteacher"))
    assert resp.status_code == 201
    assert resp.json()["role"] == "teacher"


async def test_second_registration_refused_with_admin_message(client):
    await client.post("/api/auth/register", json=_payload("firstteacher"))
    resp = await client.post("/api/auth/register", json=_payload("secondteacher"))
    assert resp.status_code == 403
    assert "administrator" in resp.json()["detail"].lower()


async def test_second_registration_allowed_with_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_teacher_registration", True)
    await client.post("/api/auth/register", json=_payload("firstteacher"))
    resp = await client.post("/api/auth/register", json=_payload("secondteacher"))
    assert resp.status_code == 201
