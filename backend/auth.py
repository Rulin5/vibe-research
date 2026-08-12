"""Password, opaque session, origin, and CSRF primitives for private APIs."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_session
from models import SessionRecord, User
from runtime_security import is_public_mode, require_secure_cookie


SESSION_COOKIE = "vr_session"
CSRF_COOKIE = "vr_csrf"
SESSION_TTL = timedelta(days=7)
_PASSWORD_HASHER = PasswordHasher(type=Type.ID)


def allowed_origins(raw: str | None = None) -> list[str]:
    value = raw if raw is not None else os.environ.get("VR_ALLOW_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
    if not origins or "*" in origins:
        raise RuntimeError("VR_ALLOW_ORIGINS must list explicit origins when credential cookies are enabled")
    return origins


def cookie_secure() -> bool:
    if is_public_mode():
        require_secure_cookie()
        return True
    return os.environ.get("VR_COOKIE_SECURE", "false").strip().lower() == "true"


def validate_registration(username: str, password: str, phone: str) -> tuple[str, str, str]:
    normalized = (username or "").strip()
    normalized_phone = (phone or "").strip()
    if not normalized:
        raise HTTPException(422, "用户名不能为空")
    if not password:
        raise HTTPException(422, "密码不能为空")
    if not normalized_phone:
        raise HTTPException(422, "手机号不能为空")
    return normalized, password, normalized_phone


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(encoded, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        SessionRecord(
            user_id=user_id,
            token_hash=_token_hash(token),
            expires_at=datetime.now(timezone.utc) + SESSION_TTL,
        )
    )
    return token


def set_auth_cookies(response: Response, session_token: str) -> None:
    secure = cookie_secure()
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(24),
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    secure = cookie_secure()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite="lax")


def _require_trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in allowed_origins():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "请求来源不被允许")


def require_csrf(request: Request) -> None:
    _require_trusted_origin(request)
    expected = request.cookies.get(CSRF_COOKIE, "")
    supplied = request.headers.get("X-CSRF-Token", "")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF 校验失败")


def require_current_user(request: Request, db: Session = Depends(get_session)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    now = datetime.now(timezone.utc)
    statement = (
        select(User)
        .join(SessionRecord, SessionRecord.user_id == User.id)
        .where(
            SessionRecord.token_hash == _token_hash(token),
            SessionRecord.revoked_at.is_(None),
            SessionRecord.expires_at > now,
        )
    )
    user = db.execute(statement).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效")
    request.state.user_fingerprint = hashlib.sha256(str(user.id).encode("utf-8")).hexdigest()[:16]
    return user


def revoke_current_session(request: Request, db: Session) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return
    row = db.execute(select(SessionRecord).where(SessionRecord.token_hash == _token_hash(token))).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
