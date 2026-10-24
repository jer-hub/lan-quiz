"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

DEFAULT_MASTERY_THRESHOLD = 80  # a class's mastery threshold until its teacher changes it, in percent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Teacher account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="teacher", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    quizzes: Mapped[list[Quiz]] = relationship("Quiz", back_populates="teacher")
    classes: Mapped[list[ClassRoom]] = relationship("ClassRoom", back_populates="teacher")


class Quiz(Base):
    """Persisted quiz definition."""

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    teacher: Mapped[User | None] = relationship("User", back_populates="quizzes")
    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    # Delete assignments with the quiz; passive_deletes lets DB ON DELETE CASCADE
    # run instead of ORM trying to SET assignments.quiz_id = NULL (NOT NULL).
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment",
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Question(Base):
    """A single quiz question with options."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    options_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    correct_indices_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    time_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="mc", nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="questions")
    # Loaded with every question (selectin) so callers can read topic_names without extra queries.
    topic_links: Mapped[list[QuestionTopic]] = relationship(
        "QuestionTopic",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="QuestionTopic.position",
    )

    @property
    def topic_names(self) -> list[str]:
        """This question's topics, in the order the teacher gave them."""
        return [link.topic.name for link in self.topic_links]


class Topic(Base):
    """A teacher's label for what a question tests. Normalization lives in app.topics."""

    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("teacher_id", "key", name="uq_teacher_topic_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Display name: trimmed, internal whitespace collapsed, first spelling the teacher used.
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Case-insensitive identity of the topic within the teacher's topics.
    key: Mapped[str] = mapped_column(String(80), nullable=False)


class QuestionTopic(Base):
    """Link between a question and one of its topics, in the order the teacher gave them."""

    __tablename__ = "question_topics"

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    topic: Mapped[Topic] = relationship("Topic", lazy="selectin")


class ClassRoom(Base):
    """A teacher's class with rostered students."""

    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    join_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    require_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    # Percent accuracy (1-100) at which the mastery report marks a topic mastered.
    mastery_threshold: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_MASTERY_THRESHOLD, server_default=str(DEFAULT_MASTERY_THRESHOLD), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    teacher: Mapped[User] = relationship("User", back_populates="classes")
    students: Mapped[list[Student]] = relationship(
        "Student", back_populates="classroom", cascade="all, delete-orphan"
    )
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment", back_populates="classroom", cascade="all, delete-orphan"
    )


class Student(Base):
    """Rostered student within a class."""

    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("class_id", "student_code", name="uq_class_student_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    student_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    classroom: Mapped[ClassRoom] = relationship("ClassRoom", back_populates="students")
    results: Mapped[list[GameResult]] = relationship("GameResult", back_populates="student")


class Assignment(Base):
    """Quiz assigned to a class."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open|closed
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = unlimited
    score_policy: Mapped[str] = mapped_column(String(20), default="best", nullable=False)  # best|latest
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    classroom: Mapped[ClassRoom] = relationship("ClassRoom", back_populates="assignments")
    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="assignments")
    histories: Mapped[list[GameHistory]] = relationship(
        "GameHistory",
        back_populates="assignment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GameHistory(Base):
    """Finished game results for later review."""

    __tablename__ = "game_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pin: Mapped[str] = mapped_column(String(10), nullable=False)
    quiz_id: Mapped[int | None] = mapped_column(
        ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True
    )
    quiz_title: Mapped[str] = mapped_column(String(200), nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    results_json: Mapped[str] = mapped_column(Text, nullable=False)
    questions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    player_count: Mapped[int] = mapped_column(Integer, default=0)

    assignment: Mapped[Assignment | None] = relationship("Assignment", back_populates="histories")
    result_rows: Mapped[list[GameResult]] = relationship(
        "GameResult", back_populates="history", cascade="all, delete-orphan"
    )


class GameResult(Base):
    """Normalized per-player result for gradebook queries."""

    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    history_id: Mapped[int] = mapped_column(
        ForeignKey("game_history.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nickname: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    history: Mapped[GameHistory] = relationship("GameHistory", back_populates="result_rows")
    student: Mapped[Student | None] = relationship("Student", back_populates="results")


class Attempt(Base):
    """Self-paced homework attempt (async, no host)."""

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnswerRecord(Base):
    """One classroom student's answer to one question, kept as evidence for the mastery report.

    Topics and correctness are recorded when the answer is given, never looked up later (ADR 0001).
    Writing and reading these rows lives in app.mastery.
    """

    __tablename__ = "answer_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    # The question's topic names when it was answered, as a JSON list; [] for a question without topics.
    topics_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # app.mastery.ANSWER_SOURCE_HOMEWORK or ANSWER_SOURCE_LIVE
    # The homework attempt or game history the answer came from; evidence outlives either.
    attempt_id: Mapped[int | None] = mapped_column(
        ForeignKey("attempts.id", ondelete="SET NULL"), nullable=True
    )
    history_id: Mapped[int | None] = mapped_column(
        ForeignKey("game_history.id", ondelete="SET NULL"), nullable=True
    )
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ActiveGame(Base):
    """Crash-safe snapshot of a live lobby (restored on startup)."""

    __tablename__ = "active_games"

    pin: Mapped[str] = mapped_column(String(10), primary_key=True)
    quiz_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quiz_title: Mapped[str] = mapped_column(String(200), nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assignment_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    requires_student_code: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="lobby", nullable=False)
    current_question_index: Mapped[int] = mapped_column(Integer, default=-1, nullable=False)
    questions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    players_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    question_history_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
