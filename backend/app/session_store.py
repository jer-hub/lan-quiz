"""Persist/restore live lobby snapshots (crash-safe PIN)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

logger = logging.getLogger(__name__)


async def save_snapshot(session) -> None:
    """Upsert ActiveGame row. Never raises (snapshot is best-effort)."""
    try:
        from app.database import AsyncSessionLocal
        from app.models import ActiveGame

        snap = session.to_snapshot()
        async with AsyncSessionLocal() as db:
            row = await db.get(ActiveGame, snap["pin"])
            payload = {
                "quiz_id": snap["quiz_id"],
                "quiz_title": snap["quiz_title"],
                "teacher_id": snap.get("teacher_id"),
                "class_id": snap.get("class_id"),
                "assignment_id": snap.get("assignment_id"),
                "requires_student_code": snap.get("requires_student_code", False),
                "status": snap.get("status", "lobby"),
                "current_question_index": snap.get("current_question_index", -1),
                "questions_json": json.dumps(snap.get("questions", []), ensure_ascii=False),
                "players_json": json.dumps(snap.get("players", []), ensure_ascii=False),
                "question_history_json": json.dumps(snap.get("question_history", []), ensure_ascii=False),
                "updated_at": datetime.now(timezone.utc),
            }
            if row is None:
                db.add(ActiveGame(pin=snap["pin"], **payload))
            else:
                for k, v in payload.items():
                    setattr(row, k, v)
            await db.commit()
    except Exception:
        logger.exception("Snapshot save failed pin=%s", getattr(session, "pin", "?"))


async def delete_snapshot(pin: str) -> None:
    try:
        from app.database import AsyncSessionLocal
        from app.models import ActiveGame

        async with AsyncSessionLocal() as db:
            row = await db.get(ActiveGame, pin.upper())
            if row is not None:
                await db.delete(row)
                await db.commit()
    except Exception:
        logger.exception("Snapshot delete failed pin=%s", pin)


async def load_snapshots() -> list[dict]:
    """Return raw snapshot dicts for startup restore."""
    from app.database import AsyncSessionLocal
    from app.models import ActiveGame

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ActiveGame))
        out = []
        for row in result.scalars().all():
            try:
                out.append(
                    {
                        "pin": row.pin,
                        "quiz_id": row.quiz_id,
                        "quiz_title": row.quiz_title,
                        "teacher_id": row.teacher_id,
                        "class_id": row.class_id,
                        "assignment_id": row.assignment_id,
                        "requires_student_code": row.requires_student_code,
                        "status": row.status,
                        "current_question_index": row.current_question_index,
                        "questions": json.loads(row.questions_json or "[]"),
                        "players": json.loads(row.players_json or "[]"),
                        "question_history": json.loads(
                            getattr(row, "question_history_json", None) or "[]"
                        ),
                    }
                )
            except Exception:
                logger.exception("Skipping corrupt snapshot pin=%s", row.pin)
        return out
