"""Migration 0006 (classes.require_password): adds the column, and never swallows a failure."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


@pytest.fixture
def migrated_at_0005(tmp_path, monkeypatch):
    """A database migrated to 0005, with the require_password column removed (pre-0006 schema)."""
    db_path = tmp_path / "lanquiz.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    command.upgrade(_alembic_cfg(), "0005_history_questions")
    raw = sqlite3.connect(db_path)
    raw.execute("ALTER TABLE classes DROP COLUMN require_password")
    raw.commit()
    raw.close()
    return url


def _classes_columns(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return {c["name"] for c in sa.inspect(engine).get_columns("classes")}
    finally:
        engine.dispose()


def test_upgrade_from_0005_adds_require_password_column(migrated_at_0005):
    assert "require_password" not in _classes_columns(migrated_at_0005)

    command.upgrade(_alembic_cfg(), "head")

    assert "require_password" in _classes_columns(migrated_at_0005)


def test_failed_column_add_is_not_silently_swallowed(tmp_path, monkeypatch):
    """With no classes table, the add must fail loudly instead of passing quietly."""
    db_path = tmp_path / "broken.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    command.upgrade(_alembic_cfg(), "0005_history_questions")
    raw = sqlite3.connect(db_path)
    raw.execute("DROP TABLE classes")
    raw.commit()
    raw.close()

    with pytest.raises(Exception):
        command.upgrade(_alembic_cfg(), "0006_class_password")
