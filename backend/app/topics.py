"""Topics: normalization and a teacher's topic vocabulary.

A topic is stored once per teacher. Names are trimmed with internal whitespace
collapsed, and two names are the same topic when they match case-insensitively;
the first spelling a teacher used is kept for display.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Topic

TOPIC_MAX_LENGTH = 80
TOPICS_PER_QUESTION_MAX = 10


def normalize_topic(name: str) -> str:
    """Trim and collapse internal whitespace: "  long   division " -> "long division"."""
    return " ".join(str(name).split())


def topic_key(name: str) -> str:
    """Case-insensitive identity of a topic name."""
    return normalize_topic(name).casefold()


def normalize_topics(names: Iterable[str]) -> list[str]:
    """Normalize a question's topics, dropping blanks and same-topic repeats, keeping order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in names:
        name = normalize_topic(raw)
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


async def resolve_topics(db: AsyncSession, teacher_id: int, names: Iterable[str]) -> list[Topic]:
    """Return the teacher's Topic rows for these names, creating any that are new."""
    wanted = normalize_topics(names)
    if not wanted:
        return []
    keys = [n.casefold() for n in wanted]
    result = await db.execute(select(Topic).where(Topic.teacher_id == teacher_id, Topic.key.in_(keys)))
    by_key = {t.key: t for t in result.scalars().all()}
    topics: list[Topic] = []
    for name, key in zip(wanted, keys):
        topic = by_key.get(key)
        if topic is None:
            topic = Topic(teacher_id=teacher_id, name=name, key=key)
            db.add(topic)
            by_key[key] = topic
        topics.append(topic)
    return topics


async def list_teacher_topics(db: AsyncSession, teacher_id: int) -> list[str]:
    """The teacher's topic names, for suggestions in the question editor."""
    result = await db.execute(select(Topic.name).where(Topic.teacher_id == teacher_id).order_by(Topic.key))
    return list(result.scalars().all())
