"""Regression: running migrations at startup must not switch off the app's loggers.

The startup migration loads Alembic's logging config. With the default
disable_existing_loggers=True that silenced uvicorn's access log and every
app warning, including AI provider failures.
"""

import asyncio
import logging

from app.database import _run_alembic_upgrade


def test_startup_migration_keeps_existing_loggers_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{tmp_path / 'probe.db'}")
    app_logger = logging.getLogger("app.routers.ai")
    access_logger = logging.getLogger("uvicorn.access")
    app_logger.disabled = False
    access_logger.disabled = False

    asyncio.run(_run_alembic_upgrade())

    assert app_logger.disabled is False
    assert access_logger.disabled is False
