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
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.NullHandler()
    root.addHandler(handler)  # the app has configured logging, as at startup
    try:
        asyncio.run(_run_alembic_upgrade())

        assert app_logger.disabled is False
        assert access_logger.disabled is False
        # alembic.ini sets the root level to WARN; it must not hide the app's INFO lines.
        assert root.level == logging.INFO
    finally:
        root.removeHandler(handler)
