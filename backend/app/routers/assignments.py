"""Assignment and gradebook routes."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_student, require_teacher, get_current_principal, TokenPrincipal
from app.database import get_db
from app.game_manager import game_manager
from app.models import Assignment, ClassRoom, GameHistory, GameResult, Quiz, Student, User
from app.schemas import (
    AssignmentCreate,
    AssignmentLiveOut,
    AssignmentOut,
    AssignmentResultRow,
    AssignmentResultsOut,
    AssignmentUpdate,
    GradebookCell,
    GradebookOut,
    GradebookRow,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assignments", tags=["assignments"])
gradebook_router = APIRouter(prefix="/api/gradebook", tags=["gradebook"])


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _is_overdue(a: Assignment, now: datetime | None = None) -> bool:
    if a.status != "open" or not a.due_at:
        return False
    now = now or datetime.now(timezone.utc)
    return _aware(a.due_at) < now  # type: ignore[operator]


def _assignment_out(
    a: Assignment,
    *,
    best_score: int | None = None,
    play_count: int = 0,
    played: bool = False,
) -> AssignmentOut:
    return AssignmentOut(
        id=a.id,
        class_id=a.class_id,
        class_name=a.classroom.name if a.classroom else "",
        quiz_id=a.quiz_id,
        quiz_title=a.quiz.title if a.quiz else "",
        title=a.title,
        status=a.status,
        due_at=a.due_at,
        max_attempts=a.max_attempts,
        score_policy=a.score_policy or "best",
        created_at=a.created_at,
        is_overdue=_is_overdue(a),
        best_score=best_score,
        play_count=play_count,
        played=played,
    )


async def _load_teacher_assignment(
    db: AsyncSession, assignment_id: int, teacher: User
) -> Assignment:
    result = await db.execute(
        select(Assignment)
        .join(ClassRoom)
        .options(selectinload(Assignment.classroom), selectinload(Assignment.quiz))
        .where(Assignment.id == assignment_id, ClassRoom.teacher_id == teacher.id)
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


def _pick_score(
    plays: list[tuple[int, int, datetime | None]], policy: str
) -> tuple[int, int, datetime | None] | None:
    """plays: list of (score, rank, played_at)."""
    if not plays:
        return None
    if policy == "latest":
        return max(plays, key=lambda p: p[2] or datetime.min.replace(tzinfo=timezone.utc))
    return max(plays, key=lambda p: p[0])


async def _student_play_stats(
    db: AsyncSession, student_id: int, assignment_ids: list[int]
) -> dict[int, dict]:
    """Return per-assignment play lists for a student."""
    if not assignment_ids:
        return {}
    result = await db.execute(
        select(GameHistory)
        .options(selectinload(GameHistory.result_rows))
        .where(GameHistory.assignment_id.in_(assignment_ids))
    )
    raw: dict[int, list[tuple[int, int, datetime | None]]] = {aid: [] for aid in assignment_ids}
    for hist in result.scalars().all():
        if not hist.assignment_id:
            continue
        for row in hist.result_rows:
            if row.student_id == student_id:
                raw[hist.assignment_id].append((row.score, row.rank, hist.played_at))

    return {
        aid: {
            "play_count": len(plays),
            "played": len(plays) > 0,
            "plays": plays,
        }
        for aid, plays in raw.items()
    }


@router.get("", response_model=list[AssignmentOut])
async def list_assignments_teacher(
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentOut]:
    result = await db.execute(
        select(Assignment)
        .join(ClassRoom)
        .options(selectinload(Assignment.classroom), selectinload(Assignment.quiz))
        .where(ClassRoom.teacher_id == teacher.id)
        .order_by(Assignment.created_at.desc())
    )
    return [_assignment_out(a) for a in result.scalars().all()]


@router.get("/mine", response_model=list[AssignmentOut])
async def list_assignments_student(
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentOut]:
    result = await db.execute(
        select(Assignment)
        .options(selectinload(Assignment.classroom), selectinload(Assignment.quiz))
        .where(Assignment.class_id == student.class_id)
        .order_by(Assignment.created_at.desc())
    )
    assignments = list(result.scalars().all())
    stats = await _student_play_stats(db, student.id, [a.id for a in assignments])
    out: list[AssignmentOut] = []
    for a in assignments:
        st = stats.get(a.id) or {}
        plays = st.get("plays") or []
        picked = _pick_score(plays, a.score_policy or "best")
        out.append(
            _assignment_out(
                a,
                best_score=picked[0] if picked else None,
                play_count=int(st.get("play_count") or 0),
                played=bool(st.get("played")),
            )
        )
    return out


@router.get("/mine/scores")
async def student_my_scores(
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(GameResult)
        .join(GameHistory)
        .options(selectinload(GameResult.history))
        .where(GameResult.student_id == student.id)
        .order_by(GameHistory.played_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "history_id": r.history_id,
            "quiz_title": r.history.quiz_title if r.history else "",
            "assignment_id": r.history.assignment_id if r.history else None,
            "score": r.score,
            "rank": r.rank,
            "played_at": r.history.played_at if r.history else None,
        }
        for r in rows
    ]


@router.post("", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    payload: AssignmentCreate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentOut:
    class_result = await db.execute(
        select(ClassRoom).where(ClassRoom.id == payload.class_id, ClassRoom.teacher_id == teacher.id)
    )
    classroom = class_result.scalar_one_or_none()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")

    quiz_result = await db.execute(
        select(Quiz).where(Quiz.id == payload.quiz_id, Quiz.teacher_id == teacher.id)
    )
    quiz = quiz_result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    title = (payload.title or quiz.title).strip()
    assignment = Assignment(
        class_id=classroom.id,
        quiz_id=quiz.id,
        title=title,
        status="open",
        due_at=payload.due_at,
        max_attempts=payload.max_attempts,
        score_policy=payload.score_policy,
    )
    db.add(assignment)
    await db.commit()
    result = await db.execute(
        select(Assignment)
        .options(selectinload(Assignment.classroom), selectinload(Assignment.quiz))
        .where(Assignment.id == assignment.id)
    )
    assignment = result.scalar_one()
    logger.info("Assignment created id=%s class=%s quiz=%s", assignment.id, classroom.id, quiz.id)
    return _assignment_out(assignment)


@router.patch("/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentOut:
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    if payload.title is not None:
        title = payload.title.strip()
        if title:
            assignment.title = title
    if payload.clear_due_at:
        assignment.due_at = None
    elif payload.due_at is not None:
        assignment.due_at = payload.due_at
    if payload.clear_max_attempts:
        assignment.max_attempts = None
    elif payload.max_attempts is not None:
        assignment.max_attempts = payload.max_attempts
    if payload.score_policy is not None:
        assignment.score_policy = payload.score_policy
    await db.commit()
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    return _assignment_out(assignment)


@router.post("/{assignment_id}/close", response_model=AssignmentOut)
async def close_assignment(
    assignment_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentOut:
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    assignment.status = "closed"
    await db.commit()
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    return _assignment_out(assignment)


@router.post("/{assignment_id}/reopen", response_model=AssignmentOut)
async def reopen_assignment(
    assignment_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentOut:
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    assignment.status = "open"
    await db.commit()
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    return _assignment_out(assignment)


@router.delete("/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(Assignment)
        .join(ClassRoom)
        .where(Assignment.id == assignment_id, ClassRoom.teacher_id == teacher.id)
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(assignment)
    await db.commit()
    return Response(status_code=204)


@router.get("/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(
    assignment_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentOut:
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    return _assignment_out(assignment)


@router.get("/{assignment_id}/results", response_model=AssignmentResultsOut)
async def assignment_results(
    assignment_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentResultsOut:
    assignment = await _load_teacher_assignment(db, assignment_id, teacher)
    class_result = await db.execute(
        select(ClassRoom)
        .options(selectinload(ClassRoom.students))
        .where(ClassRoom.id == assignment.class_id)
    )
    classroom = class_result.scalar_one()
    students = sorted(classroom.students, key=lambda s: s.display_name.lower())

    hist_result = await db.execute(
        select(GameHistory)
        .options(selectinload(GameHistory.result_rows))
        .where(GameHistory.assignment_id == assignment_id)
    )
    plays_by_student: dict[int, list[tuple[int, int, datetime | None]]] = {}
    for hist in hist_result.scalars().all():
        for row in hist.result_rows:
            if not row.student_id:
                continue
            plays_by_student.setdefault(row.student_id, []).append(
                (row.score, row.rank, hist.played_at)
            )

    policy = assignment.score_policy or "best"
    rows: list[AssignmentResultRow] = []
    for student in students:
        plays = plays_by_student.get(student.id, [])
        picked = _pick_score(plays, policy)
        rows.append(
            AssignmentResultRow(
                student_id=student.id,
                display_name=student.display_name,
                student_code=student.student_code,
                score=picked[0] if picked else None,
                rank=picked[1] if picked else None,
                play_count=len(plays),
                last_played_at=max((p[2] for p in plays if p[2]), default=None),
            )
        )

    return AssignmentResultsOut(
        assignment_id=assignment.id,
        title=assignment.title,
        class_name=classroom.name,
        score_policy=policy,
        max_attempts=assignment.max_attempts,
        rows=rows,
    )


@router.get("/{assignment_id}/live", response_model=AssignmentLiveOut)
async def assignment_live(
    assignment_id: int,
    principal: TokenPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AssignmentLiveOut:
    result = await db.execute(
        select(Assignment)
        .options(selectinload(Assignment.classroom), selectinload(Assignment.quiz))
        .where(Assignment.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if principal.role == "teacher":
        if not assignment.classroom or assignment.classroom.teacher_id != principal.user_id:
            raise HTTPException(status_code=404, detail="Assignment not found")
    elif principal.role == "student":
        if principal.class_id != assignment.class_id:
            raise HTTPException(status_code=403, detail="Not your class assignment")
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = game_manager.get_by_assignment_id(assignment_id)
    if not session:
        return AssignmentLiveOut(active=False)
    return AssignmentLiveOut(
        active=True,
        pin=session.pin,
        status=session.status.value,
        player_count=len([p for p in session.players.values() if not p.is_host]),
        quiz_title=session.quiz_title,
    )


async def _build_gradebook(db: AsyncSession, classroom: ClassRoom) -> GradebookOut:
    assign_result = await db.execute(
        select(Assignment)
        .options(selectinload(Assignment.classroom), selectinload(Assignment.quiz))
        .where(Assignment.class_id == classroom.id)
        .order_by(Assignment.created_at.asc())
    )
    assignments = list(assign_result.scalars().all())
    policy_by_id = {a.id: (a.score_policy or "best") for a in assignments}

    students = sorted(classroom.students, key=lambda s: s.display_name.lower())

    # Collect all plays then pick by policy
    plays: dict[tuple[int, int], list[tuple[int, int, datetime | None]]] = {}
    hist_result = await db.execute(
        select(GameHistory)
        .options(selectinload(GameHistory.result_rows))
        .where(GameHistory.class_id == classroom.id)
    )
    for hist in hist_result.scalars().all():
        if not hist.assignment_id:
            continue
        for row in hist.result_rows:
            if not row.student_id:
                continue
            key = (row.student_id, hist.assignment_id)
            plays.setdefault(key, []).append((row.score, row.rank, hist.played_at))

    scores: dict[tuple[int, int], tuple[int, int, datetime | None]] = {}
    for key, plist in plays.items():
        _, aid = key
        picked = _pick_score(plist, policy_by_id.get(aid, "best"))
        if picked:
            scores[key] = picked

    rows: list[GradebookRow] = []
    for student in students:
        cells: list[GradebookCell] = []
        total = 0
        for a in assignments:
            hit = scores.get((student.id, a.id))
            if hit:
                cells.append(
                    GradebookCell(
                        assignment_id=a.id,
                        assignment_title=a.title,
                        score=hit[0],
                        rank=hit[1],
                        played_at=hit[2],
                    )
                )
                total += hit[0]
            else:
                cells.append(
                    GradebookCell(
                        assignment_id=a.id,
                        assignment_title=a.title,
                        score=None,
                        rank=None,
                        played_at=None,
                    )
                )
        rows.append(
            GradebookRow(
                student_id=student.id,
                display_name=student.display_name,
                student_code=student.student_code,
                scores=cells,
                total=total,
            )
        )

    return GradebookOut(
        class_id=classroom.id,
        class_name=classroom.name,
        assignments=[_assignment_out(a) for a in assignments],
        rows=rows,
    )


@gradebook_router.get("/{class_id}", response_model=GradebookOut)
async def get_gradebook(
    class_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> GradebookOut:
    result = await db.execute(
        select(ClassRoom)
        .options(selectinload(ClassRoom.students))
        .where(ClassRoom.id == class_id, ClassRoom.teacher_id == teacher.id)
    )
    classroom = result.scalar_one_or_none()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")
    return await _build_gradebook(db, classroom)


@gradebook_router.get("/{class_id}/export")
async def export_gradebook_csv(
    class_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    result = await db.execute(
        select(ClassRoom)
        .options(selectinload(ClassRoom.students))
        .where(ClassRoom.id == class_id, ClassRoom.teacher_id == teacher.id)
    )
    classroom = result.scalar_one_or_none()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")
    book = await _build_gradebook(db, classroom)

    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ["student_code", "display_name"] + [a.title for a in book.assignments] + ["total"]
    writer.writerow(header)
    for row in book.rows:
        line = [row.student_code, row.display_name]
        for cell in row.scores:
            line.append("" if cell.score is None else cell.score)
        line.append(row.total)
        writer.writerow(line)

    buf.seek(0)
    filename = f"gradebook-class-{class_id}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
