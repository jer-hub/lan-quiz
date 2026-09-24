"""Pydantic schemas for API and Socket.IO payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QuestionCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    image: str | None = None
    options: list[str] = Field(..., min_length=2, max_length=6)
    correct_indices: list[int] = Field(..., min_length=1)
    time_limit: int = Field(default=20, ge=5, le=120)

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[str]) -> list[str]:
        cleaned = [o.strip() for o in v]
        if any(not o for o in cleaned):
            raise ValueError("Options cannot be empty")
        return cleaned

    @field_validator("correct_indices")
    @classmethod
    def validate_correct(cls, v: list[int], info: Any) -> list[int]:
        options = info.data.get("options") or []
        for idx in v:
            if idx < 0 or idx >= len(options):
                raise ValueError(f"correct_indices out of range: {idx}")
        return sorted(set(v))


class QuestionOut(QuestionCreate):
    id: int
    order_index: int = 0


class QuizCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    questions: list[QuestionCreate] = Field(default_factory=list)


class QuizUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    questions: list[QuestionCreate] | None = None


class QuizSummary(BaseModel):
    id: int
    title: str
    description: str
    question_count: int
    created_at: datetime
    updated_at: datetime
    teacher_id: int | None = None


class QuizOut(BaseModel):
    id: int
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    teacher_id: int | None = None
    questions: list[QuestionOut]


class QuizImport(BaseModel):
    title: str
    description: str = ""
    questions: list[QuestionCreate]


class TeacherRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=6, max_length=128)


class TeacherLogin(BaseModel):
    username: str
    password: str


class StudentLogin(BaseModel):
    student_code: str = Field(..., min_length=1, max_length=40)
    password: str = Field(..., min_length=1, max_length=128)
    join_code: str | None = Field(default=None, max_length=12)


class AuthUserOut(BaseModel):
    role: str
    token: str
    user_id: int | None = None
    username: str | None = None
    student_id: int | None = None
    class_id: int | None = None
    display_name: str | None = None
    class_name: str | None = None


class MeOut(BaseModel):
    role: str
    user_id: int | None = None
    username: str | None = None
    student_id: int | None = None
    class_id: int | None = None
    display_name: str | None = None
    class_name: str | None = None


class ClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ClassUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ClassOut(BaseModel):
    id: int
    name: str
    join_code: str
    student_count: int
    created_at: datetime


class StudentCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    student_code: str = Field(..., min_length=1, max_length=40)
    password: str | None = Field(default=None, min_length=1, max_length=128)


class StudentUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=1, max_length=128)


class StudentOut(BaseModel):
    id: int
    class_id: int
    display_name: str
    student_code: str
    created_at: datetime


class AssignmentCreate(BaseModel):
    class_id: int
    quiz_id: int
    title: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=50)
    score_policy: str = Field(default="best", max_length=20)

    @field_validator("score_policy")
    @classmethod
    def validate_score_policy(cls, v: str) -> str:
        policy = (v or "best").strip().lower()
        if policy not in ("best", "latest"):
            raise ValueError("score_policy must be 'best' or 'latest'")
        return policy


class AssignmentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = None
    clear_due_at: bool = False
    max_attempts: int | None = Field(default=None, ge=1, le=50)
    clear_max_attempts: bool = False
    score_policy: str | None = Field(default=None, max_length=20)

    @field_validator("score_policy")
    @classmethod
    def validate_score_policy(cls, v: str | None) -> str | None:
        if v is None:
            return v
        policy = v.strip().lower()
        if policy not in ("best", "latest"):
            raise ValueError("score_policy must be 'best' or 'latest'")
        return policy


class AssignmentOut(BaseModel):
    id: int
    class_id: int
    class_name: str
    quiz_id: int
    quiz_title: str
    title: str
    status: str
    due_at: datetime | None
    max_attempts: int | None = None
    score_policy: str = "best"
    created_at: datetime
    is_overdue: bool = False
    # Student enrichment (optional on teacher list)
    best_score: int | None = None
    play_count: int = 0
    played: bool = False


class AssignmentResultRow(BaseModel):
    student_id: int
    display_name: str
    student_code: str
    score: int | None
    rank: int | None
    play_count: int
    last_played_at: datetime | None


class AssignmentResultsOut(BaseModel):
    assignment_id: int
    title: str
    class_name: str
    score_policy: str
    max_attempts: int | None
    rows: list[AssignmentResultRow]


class AssignmentLiveOut(BaseModel):
    active: bool
    pin: str | None = None
    status: str | None = None
    player_count: int = 0
    quiz_title: str | None = None


class GameHistoryOut(BaseModel):
    id: int
    pin: str
    quiz_id: int | None
    quiz_title: str
    played_at: datetime
    player_count: int
    results: list[dict[str, Any]]
    teacher_id: int | None = None
    class_id: int | None = None
    assignment_id: int | None = None


class GradebookCell(BaseModel):
    assignment_id: int
    assignment_title: str
    score: int | None
    rank: int | None
    played_at: datetime | None


class GradebookRow(BaseModel):
    student_id: int
    display_name: str
    student_code: str
    scores: list[GradebookCell]
    total: int


class GradebookOut(BaseModel):
    class_id: int
    class_name: str
    assignments: list[AssignmentOut]
    rows: list[GradebookRow]


class HealthOut(BaseModel):
    status: str
    app: str
