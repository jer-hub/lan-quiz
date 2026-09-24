"""Auth routes for teachers and students."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import (
    TokenPrincipal,
    get_current_principal,
    hash_password,
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
