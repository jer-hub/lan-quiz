"""SQLite database setup for LanQuiz."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

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


async def init_db() -> None:
    """Create tables if they do not exist and apply lightweight SQLite column patches."""
    from app import models  # noqa: F401
    from sqlalchemy import text

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite create_all does not add columns to existing tables
        for ddl in (
            "ALTER TABLE assignments ADD COLUMN max_attempts INTEGER",
            "ALTER TABLE assignments ADD COLUMN score_policy VARCHAR(20) DEFAULT 'best'",
        ):
            try:
                await conn.execute(text(ddl))
            except Exception:
                pass  # column already exists
    logger.info("Database initialized at %s", settings.database_url)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
