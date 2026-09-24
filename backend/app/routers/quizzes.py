"""Quiz CRUD and import/export routes (teacher-owned)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_teacher
from app.database import get_db
from app.models import Assignment, Question, Quiz, User
from app.schemas import (
    QuizCreate,
    QuizImport,
    QuizOut,
    QuizSummary,
    QuizUpdate,
    QuestionCreate,
    QuestionOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


def _options_to_json(options: list[str]) -> str:
    return json.dumps(options, ensure_ascii=False)


def _indices_to_json(indices: list[int]) -> str:
    return json.dumps(indices)


def _question_to_out(q: Question) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        text=q.text,
        image=q.image,
        options=json.loads(q.options_json),
        correct_indices=json.loads(q.correct_indices_json),
        time_limit=q.time_limit,
        order_index=q.order_index,
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


def _replace_questions(quiz: Quiz, questions: list[QuestionCreate]) -> None:
    quiz.questions.clear()
    for i, q in enumerate(questions):
        quiz.questions.append(
            Question(
                text=q.text,
                image=q.image,
                options_json=_options_to_json(q.options),
                correct_indices_json=_indices_to_json(q.correct_indices),
                time_limit=q.time_limit,
                order_index=i,
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


@router.post("", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    payload: QuizCreate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuizOut:
    quiz = Quiz(title=payload.title, description=payload.description, teacher_id=teacher.id)
    _replace_questions(quiz, payload.questions)
    db.add(quiz)
    await db.commit()
    quiz = await _load_owned_quiz(db, quiz.id, teacher)
    logger.info("Quiz created id=%s title=%s teacher=%s", quiz.id, quiz.title, teacher.id)
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
        _replace_questions(quiz, payload.questions)
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
                "options": json.loads(q.options_json),
                "correct_indices": json.loads(q.correct_indices_json),
                "time_limit": q.time_limit,
            }
            for q in quiz.questions
        ],
    }


@router.post("/import", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def import_quiz(
    payload: QuizImport,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuizOut:
    quiz = Quiz(title=payload.title, description=payload.description, teacher_id=teacher.id)
    _replace_questions(quiz, payload.questions)
    db.add(quiz)
    await db.commit()
    quiz = await _load_owned_quiz(db, quiz.id, teacher)
    logger.info("Quiz imported id=%s title=%s", quiz.id, quiz.title)
    return _quiz_to_out(quiz)
