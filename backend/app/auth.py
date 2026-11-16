"""Authentication: password hashing + stateless JWT with a revocation counter.

Logout increments `User.token_version`, so every token minted before the logout
stops working immediately — a real server-side logout rather than just a client
forgetting its string.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .db import get_db

PBKDF2_ROUNDS = 260_000
MIN_PASSWORD = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


def create_token(user: models.User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "tv": user.token_version,
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "session expired — sign in again") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid session") from exc


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "not signed in")
    payload = _decode(authorization.split(" ", 1)[1].strip())
    user = db.get(models.User, int(payload.get("sub", 0)))
    if user is None:
        raise HTTPException(401, "account no longer exists")
    if int(payload.get("tv", -1)) != user.token_version:
        raise HTTPException(401, "session revoked — sign in again")
    return user


def current_student(
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> models.Student:
    student = db.scalars(select(models.Student).where(models.Student.user_id == user.id)).first()
    if student is None:
        raise HTTPException(409, "profile not created — finish onboarding")
    return student


def owned_course(db: Session, student_id: int, course_id: int) -> models.Course:
    course = db.get(models.Course, course_id)
    if course is None or course.student_id != student_id:
        raise HTTPException(404, "course not found")
    return course
