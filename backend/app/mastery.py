"""Mastery: recording answers as evidence, and the per-class mastery report.

Every answer by a classroom student is recorded once, with the topics its question had and
whether it was correct at that moment (ADR 0001). The report reads only those records.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerRecord, ClassRoom
from app.schemas import MasteryCell, MasteryReportOut, MasteryRow
from app.topics import topic_key

MASTERY_WINDOW = 10  # accuracy is over a student's most recent answers on a topic, at most this many
MASTERY_MIN_ANSWERS = 3  # with fewer answers on a topic, the report says "not enough answers"
DEFAULT_MASTERY_THRESHOLD = 80  # percent accuracy at which a topic counts as mastered


@dataclass(frozen=True)
class GivenAnswer:
    """One answer to record: the question's topics when answered, and whether it was correct."""

    topics: list[str]
    correct: bool


def record_answers(
    db: AsyncSession,
    *,
    student_id: int,
    class_id: int,
    answers: Iterable[GivenAnswer],
    answered_at: datetime,
    attempt_id: int | None = None,
    history_id: int | None = None,
) -> None:
    """Add one answer record per answer to the session; the caller commits with its own work.

    Pass attempt_id for a homework attempt or history_id for a live game.
    """
    source = "homework" if attempt_id is not None else "live"
    for answer in answers:
        db.add(
            AnswerRecord(
                student_id=student_id,
                class_id=class_id,
                topics_json=json.dumps(list(answer.topics), ensure_ascii=False),
                correct=answer.correct,
                source=source,
                attempt_id=attempt_id,
                history_id=history_id,
                answered_at=answered_at,
            )
        )


def mastery_threshold(classroom: ClassRoom) -> int:
    """The class's mastery threshold, a whole-number percentage. Fixed for now; per-class setting is #16."""
    return DEFAULT_MASTERY_THRESHOLD


def _cell(topic: str, given: list[bool], threshold: int) -> MasteryCell:
    """A student's cell for one topic from their counted answers, most recent first."""
    if len(given) < MASTERY_MIN_ANSWERS:
        return MasteryCell(topic=topic, answer_count=len(given), accuracy=None, mastered=False)
    correct = sum(given)
    return MasteryCell(
        topic=topic,
        answer_count=len(given),
        accuracy=round(100 * correct / len(given), 1),
        # Compare exactly, not the rounded accuracy, so 79.96% never reads as mastered.
        mastered=100 * correct >= threshold * len(given),
    )


async def build_mastery_report(db: AsyncSession, classroom: ClassRoom) -> MasteryReportOut:
    """The mastery report for a class whose students are loaded."""
    students = sorted(classroom.students, key=lambda s: s.display_name.lower())
    result = await db.execute(
        select(AnswerRecord)
        .where(
            AnswerRecord.class_id == classroom.id,
            # Only the current roster: a student who left the class drops out of the report.
            AnswerRecord.student_id.in_([s.id for s in students]),
        )
        .order_by(AnswerRecord.answered_at.desc(), AnswerRecord.id.desc())
    )
    # (student, topic key) -> correctness of each answer, most recent first.
    answers: dict[tuple[int, str], list[bool]] = {}
    names: dict[str, str] = {}
    untagged = 0
    for record in result.scalars().all():
        topics = json.loads(record.topics_json or "[]")
        if not topics:
            untagged += 1
        for name in topics:
            key = topic_key(name)
            names.setdefault(key, name)
            answers.setdefault((record.student_id, key), []).append(record.correct)

    threshold = mastery_threshold(classroom)
    topic_keys = sorted(names)
    rows: list[MasteryRow] = []
    for student in students:
        cells = []
        for key in topic_keys:
            given = answers.get((student.id, key), [])[:MASTERY_WINDOW]
            cells.append(_cell(names[key], given, threshold))
        rows.append(
            MasteryRow(
                student_id=student.id,
                display_name=student.display_name,
                student_code=student.student_code,
                cells=cells,
            )
        )
    return MasteryReportOut(
        class_id=classroom.id,
        class_name=classroom.name,
        mastery_threshold=threshold,
        window=MASTERY_WINDOW,
        min_answers=MASTERY_MIN_ANSWERS,
        topics=[names[k] for k in topic_keys],
        rows=rows,
        untagged_answer_count=untagged,
    )
