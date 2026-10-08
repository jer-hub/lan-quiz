"""SQLite database setup for LanQuiz."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Enforce FK cascades on SQLite (off by default)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


async def _run_alembic_upgrade() -> None:
    """Run `alembic upgrade head` against the sync SQLite URL."""
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    # env.py resolves the URL itself (respects ALEMBIC_DATABASE_URL).
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Migrate (Alembic) with create_all fallback for fresh/minimal envs."""
    from app import models  # noqa: F401

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    try:
        await _run_alembic_upgrade()
    except Exception as exc:  # alembic missing or migration error
        logger.warning("Alembic upgrade failed, falling back to create_all: %s", exc)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized at %s", settings.database_url)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
