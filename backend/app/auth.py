"""Authentication helpers: password hashing and JWT."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Student, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

Role = Literal["teacher", "student"]


class TokenPrincipal(BaseModel):
    role: Role
    user_id: int | None = None
    student_id: int | None = None
    class_id: int | None = None
    username: str | None = None
    display_name: str | None = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(claims: dict[str, Any], hours: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=hours or settings.jwt_expire_hours)
    payload = {**claims, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def principal_from_payload(payload: dict[str, Any]) -> TokenPrincipal:
    role = payload.get("role")
    if role not in ("teacher", "student"):
        raise HTTPException(status_code=401, detail="Invalid token role")
    return TokenPrincipal(
        role=role,
        user_id=payload.get("user_id"),
        student_id=payload.get("student_id"),
        class_id=payload.get("class_id"),
        username=payload.get("username"),
        display_name=payload.get("display_name"),
    )


async def get_optional_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TokenPrincipal | None:
    if not creds:
        return None
    return principal_from_payload(decode_token(creds.credentials))


async def get_current_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TokenPrincipal:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return principal_from_payload(decode_token(creds.credentials))


async def require_teacher(
    principal: Annotated[TokenPrincipal, Depends(get_current_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if principal.role != "teacher" or not principal.user_id:
        raise HTTPException(status_code=403, detail="Teachers only")
    result = await db.execute(select(User).where(User.id == principal.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_student(
    principal: Annotated[TokenPrincipal, Depends(get_current_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Student:
    if principal.role != "student" or not principal.student_id:
        raise HTTPException(status_code=403, detail="Students only")
    result = await db.execute(select(Student).where(Student.id == principal.student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=401, detail="Student not found")
    return student


def teacher_token(user: User) -> str:
    return create_access_token(
        {
            "role": "teacher",
            "user_id": user.id,
            "username": user.username,
            "sub": f"user:{user.id}",
        }
    )


def student_token(student: Student) -> str:
    return create_access_token(
        {
            "role": "student",
            "student_id": student.id,
            "class_id": student.class_id,
            "display_name": student.display_name,
            "sub": f"student:{student.id}",
        }
    )


def decode_socket_token(token: str | None) -> TokenPrincipal | None:
    """Decode JWT from Socket.IO auth without raising HTTP errors."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return principal_from_payload(payload)
    except Exception:
        return None
