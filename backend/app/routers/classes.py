"""Class and roster management (teachers)."""

from __future__ import annotations

import csv
import io
import logging
import secrets
import string
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import hash_password, require_teacher
from app.database import get_db
from app.models import ClassRoom, Student, User
from app.schemas import (
    ClassCreate,
    ClassOut,
    ClassUpdate,
    StudentCreate,
    StudentCreated,
    StudentOut,
    StudentUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/classes", tags=["classes"])

STUDENT_PASSWORD_MIN = 6
GENERATED_PASSWORD_LENGTH = 10


def _gen_join_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _gen_student_password(code: str) -> str:
    """Random password from an unambiguous alphabet. Never equal to the student code."""
    alphabet = string.ascii_letters + string.digits
    for ch in "O0Il1":
        alphabet = alphabet.replace(ch, "")
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(GENERATED_PASSWORD_LENGTH))
        if pw.upper() != code.upper():
            return pw


def _class_out(c: ClassRoom) -> ClassOut:
    return ClassOut(
        id=c.id,
        name=c.name,
        join_code=c.join_code,
        student_count=len(c.students) if c.students is not None else 0,
        require_password=c.require_password,
        created_at=c.created_at,
    )


def _student_out(s: Student) -> StudentOut:
    return StudentOut(
        id=s.id,
        class_id=s.class_id,
        display_name=s.display_name,
        student_code=s.student_code,
        created_at=s.created_at,
    )


async def _load_class(db: AsyncSession, class_id: int, teacher: User) -> ClassRoom:
    result = await db.execute(
        select(ClassRoom)
        .options(selectinload(ClassRoom.students))
        .where(ClassRoom.id == class_id, ClassRoom.teacher_id == teacher.id)
    )
    classroom = result.scalar_one_or_none()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")
    return classroom


@router.get("", response_model=list[ClassOut])
async def list_classes(
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[ClassOut]:
    result = await db.execute(
        select(ClassRoom)
        .options(selectinload(ClassRoom.students))
        .where(ClassRoom.teacher_id == teacher.id)
        .order_by(ClassRoom.created_at.desc())
    )
    return [_class_out(c) for c in result.scalars().all()]


@router.post("", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
async def create_class(
    payload: ClassCreate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ClassOut:
    for _ in range(20):
        code = _gen_join_code()
        exists = await db.execute(select(ClassRoom).where(ClassRoom.join_code == code))
        if not exists.scalar_one_or_none():
            break
    else:
        raise HTTPException(status_code=500, detail="Could not generate join code")

    classroom = ClassRoom(teacher_id=teacher.id, name=payload.name.strip(), join_code=code)
    db.add(classroom)
    await db.commit()
    classroom = await _load_class(db, classroom.id, teacher)
    logger.info("Class created id=%s code=%s", classroom.id, classroom.join_code)
    return _class_out(classroom)


@router.get("/{class_id}", response_model=ClassOut)
async def get_class(
    class_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ClassOut:
    return _class_out(await _load_class(db, class_id, teacher))


@router.put("/{class_id}", response_model=ClassOut)
async def update_class(
    class_id: int,
    payload: ClassUpdate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ClassOut:
    classroom = await _load_class(db, class_id, teacher)
    if payload.name is not None:
        classroom.name = payload.name.strip()
    if payload.require_password is not None:
        classroom.require_password = payload.require_password
    await db.commit()
    return _class_out(await _load_class(db, class_id, teacher))


@router.delete("/{class_id}", status_code=204)
async def delete_class(
    class_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    classroom = await _load_class(db, class_id, teacher)
    await db.delete(classroom)
    await db.commit()
    return Response(status_code=204)


@router.get("/{class_id}/students", response_model=list[StudentOut])
async def list_students(
    class_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[StudentOut]:
    classroom = await _load_class(db, class_id, teacher)
    return [_student_out(s) for s in sorted(classroom.students, key=lambda x: x.display_name.lower())]


@router.post("/{class_id}/students", response_model=StudentCreated, status_code=201)
async def add_student(
    class_id: int,
    payload: StudentCreate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> StudentCreated:
    classroom = await _load_class(db, class_id, teacher)
    code = payload.student_code.strip().upper()
    for s in classroom.students:
        if s.student_code == code:
            raise HTTPException(status_code=400, detail="Student code already in this class")
    generated: str | None = None
    password = payload.password
    if not password:
        generated = _gen_student_password(code)
        password = generated
    student = Student(
        class_id=classroom.id,
        display_name=payload.display_name.strip(),
        student_code=code,
        password_hash=hash_password(password),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return StudentCreated(**_student_out(student).model_dump(), generated_password=generated)


@router.put("/{class_id}/students/{student_id}", response_model=StudentOut)
async def update_student(
    class_id: int,
    student_id: int,
    payload: StudentUpdate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> StudentOut:
    await _load_class(db, class_id, teacher)
    result = await db.execute(
        select(Student).where(Student.id == student_id, Student.class_id == class_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if payload.display_name is not None:
        student.display_name = payload.display_name.strip()
    if payload.password is not None:
        student.password_hash = hash_password(payload.password)
    await db.commit()
    await db.refresh(student)
    return _student_out(student)


@router.delete("/{class_id}/students/{student_id}", status_code=204)
async def delete_student(
    class_id: int,
    student_id: int,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _load_class(db, class_id, teacher)
    result = await db.execute(
        select(Student).where(Student.id == student_id, Student.class_id == class_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    await db.delete(student)
    await db.commit()
    return Response(status_code=204)


ROSTER_HEADERS = [
    "username",
    "password",
    "first_name",
    "last_name",
    "email",
    "school_id",
    "class_section",
]


def parse_roster_csv(raw: str) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Validate headers (exact sequence) and map rows.

    Mapping: student_code=username (upper), password=supplied password or None
    (None means generate one at import; supplied passwords need 6+ chars),
    display_name="first_name last_name". email/school_id/class_section ignored.
    Returns (valid_rows, skipped) with 1-based file row numbers.
    """
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ValueError("Empty CSV")
    headers = [h.strip() if h else "" for h in reader.fieldnames]
    if headers != ROSTER_HEADERS:
        raise ValueError(
            "CSV must have headers in order: " + ",".join(ROSTER_HEADERS)
        )
    valid: list[dict[str, str]] = []
    skipped: list[dict[str, Any]] = []
    for lineno, row in enumerate(reader, start=2):
        username = (row.get("username") or "").strip()
        password = (row.get("password") or "").strip()
        first = (row.get("first_name") or "").strip()
        last = (row.get("last_name") or "").strip()
        name = f"{first} {last}".strip()
        code = username.upper()
        if not name or not code:
            skipped.append({"row": lineno, "reason": "missing username or name"})
            continue
        if password and len(password) < STUDENT_PASSWORD_MIN:
            skipped.append({"row": lineno, "reason": "password too short (min 6)"})
            continue
        valid.append(
            {
                "display_name": name,
                "student_code": code,
                "password": password or None,
                "lineno": lineno,
            }
        )
    return valid, skipped


@router.post("/{class_id}/students/import")
async def import_roster_csv(
    class_id: int,
    file: UploadFile,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """CSV headers (in order): username,password,first_name,last_name,email,school_id,class_section."""
    classroom = await _load_class(db, class_id, teacher)
    try:
        raw = (await file.read()).decode("utf-8-sig")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read CSV (use UTF-8)")
    try:
        rows, skipped = parse_roster_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    created: list[tuple[Student, str | None]] = []
    existing_codes = {s.student_code for s in classroom.students}
    seen_in_file: set[str] = set()
    for row in rows:
        lineno = row["lineno"]
        code = row["student_code"]
        if code in seen_in_file:
            skipped.append({"row": lineno, "reason": f"duplicate code {code} in file"})
            continue
        seen_in_file.add(code)
        if code in existing_codes:
            skipped.append({"row": lineno, "reason": f"code {code} already in class"})
            continue
        generated: str | None = None
        password = row["password"]
        if password is None:
            generated = _gen_student_password(code)
            password = generated
        student = Student(
            class_id=classroom.id,
            display_name=row["display_name"],
            student_code=code,
            password_hash=hash_password(password),
        )
        db.add(student)
        created.append((student, generated))
        existing_codes.add(code)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Import failed, no rows added")
    for s, _ in created:
        await db.refresh(s)
    return {
        "added": [
            StudentCreated(**_student_out(s).model_dump(), generated_password=g).model_dump()
            for s, g in created
        ],
        "skipped": sorted(skipped, key=lambda s: s["row"]),
    }
