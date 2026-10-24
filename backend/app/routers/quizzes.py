"""Quiz CRUD and import/export routes (teacher-owned)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth import require_teacher
from app.config import settings
from app.database import get_db
from app.models import Assignment, Question, QuestionTopic, Quiz, User
from app.schemas import (
    QuizCreate,
    QuizImport,
    QuizOut,
    QuizSummary,
    QuizUpdate,
    QuestionCreate,
    QuestionOut,
)
from app.topics import list_teacher_topics, resolve_topics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])

MAX_IMAGE_BYTES = 2_000_000
UPLOAD_IMAGE_PATH = "/api/quizzes/upload-image"
_MULTIPART_OVERHEAD = 64 * 1024  # boundaries and part headers around the file


class ImageUploadSizeLimit:
    """Refuse an oversized image upload while the body is still arriving.

    Reads the request body chunk by chunk and stops at the limit, so the
    multipart parser never receives more than about 2 MB. A declared
    Content-Length over the limit is refused without reading the body.
    The route still checks the exact file size.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != UPLOAD_IMAGE_PATH:
            await self.app(scope, receive, send)
            return
        limit = MAX_IMAGE_BYTES + _MULTIPART_OVERHEAD
        declared = dict(scope.get("headers") or []).get(b"content-length")
        try:
            if declared is not None and int(declared) > limit:
                await self._refuse(scope, receive, send)
                return
        except ValueError:
            pass  # malformed header: fall back to counting the bytes
        buffered: list[Message] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return  # client disconnected
            total += len(message.get("body", b""))
            if total > limit:
                await self._refuse(scope, receive, send)
                return
            buffered.append(message)
            if not message.get("more_body", False):
                break
        pending_messages = list(buffered)

        async def replay_receive() -> Message:
            if pending_messages:
                return pending_messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _refuse(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse({"detail": "Image too large (max 2 MB)"}, status_code=413)
        await response(scope, receive, send)


def _options_to_json(options: list[str]) -> str:
    return json.dumps(options, ensure_ascii=False)


def _indices_to_json(indices: list[int]) -> str:
    return json.dumps(indices)


def _question_to_out(q: Question) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        text=q.text,
        image=q.image,
        options=json.loads(q.options_json or "[]"),
        correct_indices=json.loads(q.correct_indices_json or "[]"),
        time_limit=q.time_limit,
        order_index=q.order_index,
        kind=q.kind or "mc",
        answer_text=q.answer_text,
        topics=q.topic_names,
    )


def _quiz_to_out(quiz: Quiz) -> QuizOut:
    return QuizOut(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
        teacher_id=quiz.teacher_id,
        questions=[_question_to_out(q) for q in quiz.questions],
    )


async def _load_owned_quiz(db: AsyncSession, quiz_id: int, teacher: User) -> Quiz:
    result = await db.execute(
        select(Quiz)
        .options(selectinload(Quiz.questions))
        .where(Quiz.id == quiz_id, Quiz.teacher_id == teacher.id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


async def _replace_questions(
    db: AsyncSession, quiz: Quiz, teacher: User, questions: list[QuestionCreate]
) -> None:
    quiz.questions.clear()
    for i, q in enumerate(questions):
        topics = await resolve_topics(db, teacher.id, q.topics)
        quiz.questions.append(
            Question(
                text=q.text,
                image=q.image,
                options_json=_options_to_json(q.options),
                correct_indices_json=_indices_to_json(q.correct_indices),
                time_limit=q.time_limit,
                order_index=i,
                kind=q.kind,
                answer_text=q.answer_text,
                topic_links=[QuestionTopic(topic=t, position=pos) for pos, t in enumerate(topics)],
            )
        )


@router.get("", response_model=list[QuizSummary])
async def list_quizzes(
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[QuizSummary]:
    result = await db.execute(
        select(Quiz)
        .options(selectinload(Quiz.questions))
        .where(Quiz.teacher_id == teacher.id)
        .order_by(Quiz.updated_at.desc())
    )
    quizzes = result.scalars().all()
    return [
        QuizSummary(
            id=q.id,
            title=q.title,
            description=q.description,
            question_count=len(q.questions),
            created_at=q.created_at,
            updated_at=q.updated_at,
            teacher_id=q.teacher_id,
        )
        for q in quizzes
    ]


@router.get("/topics", response_model=list[str])
async def list_topics(
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """The teacher's topics, for suggestions in the question editor."""
    return await list_teacher_topics(db, teacher.id)


@router.post("", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    payload: QuizCreate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuizOut:
    quiz = Quiz(title=payload.title, description=payload.description, teacher_id=teacher.id)
    await _replace_questions(db, quiz, teacher, payload.questions)
    db.add(quiz)
    await db.commit()
    quiz = await _load_owned_quiz(db, quiz.id, teacher)
    logger.info("Quiz created id=%s title=%s teacher=%s", quiz.id, quiz.title, teacher.id)
    return _quiz_to_out(quiz)


@router.post("/import", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def import_quiz(
    payload: QuizImport,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuizOut:
    quiz = Quiz(title=payload.title, description=payload.description, teacher_id=teacher.id)
    await _replace_questions(db, quiz, teacher, payload.questions)
    db.add(quiz)
    await db.commit()
    quiz = await _load_owned_quiz(db, quiz.id, teacher)
    logger.info("Quiz imported id=%s title=%s", quiz.id, quiz.title)
    return _quiz_to_out(quiz)


@router.get("/{quiz_id}", response_model=QuizOut)
async def get_quiz(
    quiz_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuizOut:
    return _quiz_to_out(await _load_owned_quiz(db, quiz_id, teacher))


@router.put("/{quiz_id}", response_model=QuizOut)
async def update_quiz(
    quiz_id: int,
    payload: QuizUpdate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuizOut:
    quiz = await _load_owned_quiz(db, quiz_id, teacher)
    if payload.title is not None:
        quiz.title = payload.title
    if payload.description is not None:
        quiz.description = payload.description
    if payload.questions is not None:
        await _replace_questions(db, quiz, teacher, payload.questions)
    await db.commit()
    quiz = await _load_owned_quiz(db, quiz_id, teacher)
    return _quiz_to_out(quiz)


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    quiz = await _load_owned_quiz(db, quiz_id, teacher)
    # Remove dependent assignments first so ORM does not try to NULL quiz_id
    asg = await db.execute(select(Assignment).where(Assignment.quiz_id == quiz_id))
    for assignment in asg.scalars().all():
        await db.delete(assignment)
    await db.delete(quiz)
    await db.commit()
    logger.info("Quiz deleted id=%s", quiz_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{quiz_id}/export")
async def export_quiz(
    quiz_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    quiz = await _load_owned_quiz(db, quiz_id, teacher)
    return {
        "title": quiz.title,
        "description": quiz.description,
        "questions": [
            {
                "text": q.text,
                "image": q.image,
                "options": json.loads(q.options_json or "[]"),
                "correct_indices": json.loads(q.correct_indices_json or "[]"),
                "time_limit": q.time_limit,
                "kind": q.kind or "mc",
                "answer_text": q.answer_text,
                "topics": q.topic_names,
            }
            for q in quiz.questions
        ],
    }


@router.post("/upload-image")
async def upload_image(
    file: UploadFile,
    teacher: User = Depends(require_teacher),
) -> dict[str, Any]:
    """Teacher-only image upload (2MB, png/jpg/webp). Returns {url}."""
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 2 MB)")
    ctype = (file.content_type or "").lower()
    if ctype not in ("image/png", "image/jpeg", "image/webp"):
        # Fall back to extension check for clients without content-type.
        name = (file.filename or "").lower()
        if not (name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg") or name.endswith(".webp")):
            raise HTTPException(status_code=400, detail="Only png/jpg/webp images allowed")
    try:
        from PIL import Image as _Image

        import io as _io
        import uuid as _uuid

        img = _Image.open(_io.BytesIO(data))
        img.verify()
        ext = "webp"
        uploads = settings.data_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        fname = f"{_uuid.uuid4().hex}.{ext}"
        # Re-open after verify (verify() closes the parser).
        img = _Image.open(_io.BytesIO(data))
        img.thumbnail((1600, 1600))
        img.save(uploads / fname, format="WEBP", quality=82)
        return {"url": f"/uploads/{fname}"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")
