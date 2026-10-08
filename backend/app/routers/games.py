"""Game history and info routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import analyze_questions, load_history_questions
from app.auth import require_teacher
from app.config import settings
from app.database import get_db
from app.game_manager import game_manager
from app.models import GameHistory, User
from app.schemas import GameHistoryOut

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("/pin/{pin}")
async def peek_pin(pin: str) -> dict[str, Any]:
    """Public: inspect an active game PIN (for join form UX)."""
    session = game_manager.get_by_pin(pin.strip().upper())
    if not session:
        raise HTTPException(status_code=404, detail="No active game with that PIN")
    return {
        "pin": session.pin,
        "quiz_title": session.quiz_title,
        "status": session.status.value,
        "requires_student_code": session.requires_student_code,
        "player_count": session.player_count(),
        "team_mode": session.team_mode,
        "teams": list(session.teams),
    }


def _history_out(r: GameHistory) -> GameHistoryOut:
    return GameHistoryOut(
        id=r.id,
        pin=r.pin,
        quiz_id=r.quiz_id,
        quiz_title=r.quiz_title,
        played_at=r.played_at,
        player_count=r.player_count,
        results=json.loads(r.results_json),
        teacher_id=r.teacher_id,
        class_id=r.class_id,
        assignment_id=r.assignment_id,
    )


@router.get("/history", response_model=list[GameHistoryOut])
async def list_history(
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[GameHistoryOut]:
    result = await db.execute(
        select(GameHistory)
        .where(GameHistory.teacher_id == teacher.id)
        .order_by(GameHistory.played_at.desc())
        .limit(100)
    )
    return [_history_out(r) for r in result.scalars().all()]


@router.get("/history/{history_id}", response_model=GameHistoryOut)
async def get_history(
    history_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> GameHistoryOut:
    result = await db.execute(
        select(GameHistory).where(GameHistory.id == history_id, GameHistory.teacher_id == teacher.id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="History entry not found")
    return _history_out(row)


@router.get("/history/{history_id}/analysis")
async def history_analysis(
    history_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(
        select(GameHistory).where(GameHistory.id == history_id, GameHistory.teacher_id == teacher.id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {
        "history_id": row.id,
        "pin": row.pin,
        "quiz_title": row.quiz_title,
        "analysis": analyze_questions(load_history_questions(row)),
    }


@router.delete("/history/{history_id}", status_code=204)
async def delete_history(
    history_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(GameHistory).where(GameHistory.id == history_id, GameHistory.teacher_id == teacher.id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="History entry not found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)
