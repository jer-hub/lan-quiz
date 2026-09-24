"""LanQuiz FastAPI + Socket.IO application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import ai, assignments, auth, classes, games, quizzes
from app.schemas import HealthOut
from app.socket_handlers import register_socket_handlers

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lanquiz")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info(
        "%s ready — bind %s:%s — public URL %s",
        settings.app_name,
        settings.host,
        settings.port,
        settings.public_base_url,
    )
    yield


fastapi_app = FastAPI(title=settings.app_name, lifespan=lifespan)

_cors_wildcard = settings.cors_origins.strip() == "*"
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_wildcard else settings.cors_origin_list,
    allow_credentials=not _cors_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(auth.router)
fastapi_app.include_router(quizzes.router)
fastapi_app.include_router(games.router)
fastapi_app.include_router(classes.router)
fastapi_app.include_router(assignments.router)
fastapi_app.include_router(assignments.gradebook_router)
fastapi_app.include_router(ai.router)


@fastapi_app.get("/api/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status="ok", app=settings.app_name)


# Socket.IO server wrapping FastAPI
# Important: cors_allowed_origins must be the string "*" for wildcard,
# not ["*"] — a list is matched literally and rejects browser Origins → 403.
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*" if _cors_wildcard else settings.cors_origin_list,
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
)
register_socket_handlers(sio)

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")


def _mount_frontend() -> None:
    if not STATIC_DIR.exists():
        logger.warning("Static frontend not found at %s (dev mode?)", STATIC_DIR)
        return

    assets = STATIC_DIR / "assets"
    if assets.exists():
        fastapi_app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @fastapi_app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        # Do not swallow API routes (already registered above)
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")


_mount_frontend()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
