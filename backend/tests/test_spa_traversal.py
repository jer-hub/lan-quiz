"""Regression: the SPA fallback must never serve files outside the static root."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.main import resolve_spa_target


@pytest.fixture()
def layout(tmp_path: Path) -> tuple[Path, Path]:
    """Return (static_dir, secret_file) where the secret sits outside static."""
    static = tmp_path / "backend" / "static"
    static.mkdir(parents=True)
    (static / "index.html").write_text("<html>ok</html>")
    (static / "assets.js").write_text("console.log(1)")
    secret = tmp_path / "backend" / "data" / "lanquiz.db"
    secret.parent.mkdir(parents=True)
    secret.write_text("SECRET")
    return static, secret


@pytest.mark.parametrize(
    "path",
    [
        "../data/lanquiz.db",
        "../../data/lanquiz.db",
        "/etc/passwd",
        "..",
    ],
)
def test_paths_escaping_static_root_are_404(layout, path):
    static, _ = layout
    with pytest.raises(HTTPException) as exc:
        resolve_spa_target(static, path)
    assert exc.value.status_code == 404


def test_in_root_file_is_served(layout):
    static, _ = layout
    assert resolve_spa_target(static, "assets.js") == (static / "assets.js").resolve()


def test_unknown_in_root_path_falls_back_to_index(layout):
    static, _ = layout
    assert resolve_spa_target(static, "some/client/route") == (static / "index.html").resolve()


def test_empty_path_falls_back_to_index(layout):
    static, _ = layout
    assert resolve_spa_target(static, "") == (static / "index.html").resolve()
