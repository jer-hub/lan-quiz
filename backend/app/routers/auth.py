"""Auth routes for teachers and students."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import (
    TokenPrincipal,
    get_current_principal,
    hash_password,
    require_teacher,
    student_token,
    teacher_token,
    verify_password,
)
from app.database import get_db
from app.models import ClassRoom, Student, User
from app.schemas import (
    AuthUserOut,
    MeOut,
    StudentLogin,
    TeacherLogin,
    TeacherRegister,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthUserOut, status_code=status.HTTP_201_CREATED)
async def register_teacher(payload: TeacherRegister, db: AsyncSession = Depends(get_db)) -> AuthUserOut:
    username = payload.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username too short")
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    user = User(username=username, password_hash=hash_password(payload.password), role="teacher")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Teacher registered username=%s id=%s", user.username, user.id)
    return AuthUserOut(
        role="teacher",
        token=teacher_token(user),
        user_id=user.id,
        username=user.username,
    )


@router.post("/login", response_model=AuthUserOut)
async def login_teacher(payload: TeacherLogin, db: AsyncSession = Depends(get_db)) -> AuthUserOut:
    username = payload.username.strip().lower()
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return AuthUserOut(
        role="teacher",
        token=teacher_token(user),
        user_id=user.id,
        username=user.username,
    )


@router.post("/student/login", response_model=AuthUserOut)
async def login_student(payload: StudentLogin, db: AsyncSession = Depends(get_db)) -> AuthUserOut:
    code = payload.student_code.strip().upper()
    join = (payload.join_code or "").strip().upper() or None

    query = select(Student).options(selectinload(Student.classroom))
    if join:
        result = await db.execute(
            query.join(ClassRoom).where(
                ClassRoom.join_code == join,
                Student.student_code == code,
            )
        )
        student = result.scalar_one_or_none()
    else:
        result = await db.execute(query.where(Student.student_code == code))
        matches = result.scalars().all()
        if len(matches) > 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple classes use this student code. Enter the class join code.",
            )
        student = matches[0] if matches else None

    if not student or not verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid student code or password")

    return AuthUserOut(
        role="student",
        token=student_token(student),
        student_id=student.id,
        class_id=student.class_id,
        display_name=student.display_name,
        class_name=student.classroom.name if student.classroom else None,
    )


@router.get("/me", response_model=MeOut)
async def me(
    principal: TokenPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    if principal.role == "teacher":
        return MeOut(
            role="teacher",
            user_id=principal.user_id,
            username=principal.username,
        )
    result = await db.execute(
        select(Student).options(selectinload(Student.classroom)).where(Student.id == principal.student_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=401, detail="Student not found")
    return MeOut(
        role="student",
        student_id=student.id,
        class_id=student.class_id,
        display_name=student.display_name,
        class_name=student.classroom.name if student.classroom else None,
    )


def validate_teacher_import_row(username: str, password: str) -> tuple[str, str]:
    """Return (username, password) or raise ValueError with the skip reason."""
    uname = (username or "").strip().lower()
    pwd = (password or "").strip() or uname
    if len(uname) < 3:
        raise ValueError("username too short (min 3)")
    if len(pwd) < 6:
        raise ValueError("password too short (min 6)")
    return uname, pwd


@router.post("/teachers/import")
async def import_teachers_csv(
    file: UploadFile,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Teacher-only bulk teacher import. Same headers as roster CSV (in order):
    username,password,first_name,last_name,email,school_id,class_section.
    Only username/password are used (username lowercased, min 3 chars;
    password defaults to username, min 6 chars)."""
    from app.routers.classes import ROSTER_HEADERS

    try:
        raw = (await file.read()).decode("utf-8-sig")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read CSV (use UTF-8)")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty CSV")
    headers = [h.strip() if h else "" for h in reader.fieldnames]
    if headers != ROSTER_HEADERS:
        raise HTTPException(
            status_code=400,
            detail="CSV must have headers in order: " + ",".join(ROSTER_HEADERS),
        )
    existing_result = await db.execute(select(User.username))
    existing = set(existing_result.scalars().all())
    seen_in_file: set[str] = set()
    added: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for lineno, row in enumerate(reader, start=2):
        try:
            uname, pwd = validate_teacher_import_row(
                row.get("username") or "", row.get("password") or ""
            )
        except ValueError as exc:
            skipped.append({"row": lineno, "reason": str(exc)})
            continue
        username, password = uname, pwd
        if username in seen_in_file:
            skipped.append({"row": lineno, "reason": f"duplicate username {username} in file"})
            continue
        seen_in_file.add(username)
        if username in existing:
            skipped.append({"row": lineno, "reason": f"username {username} already taken"})
            continue
        user = User(username=username, password_hash=hash_password(password), role="teacher")
        db.add(user)
        added.append({"username": username})
        existing.add(username)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Import failed, no rows added")
    ids: dict[str, int] = {}
    if added:
        result = await db.execute(
            select(User).where(User.username.in_([a["username"] for a in added]))
        )
        ids = {u.username: u.id for u in result.scalars().all()}
    return {
        "added": [{"user_id": ids.get(a["username"]), "username": a["username"]} for a in added],
        "skipped": skipped,
    }
