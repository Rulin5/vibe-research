"""Deployment-mode security policy shared by HTTP and outbound adapters."""

from __future__ import annotations

import os
import time
from functools import lru_cache

from fastapi import HTTPException, Request, status
from redis import Redis
from redis.exceptions import RedisError

from db import DatabaseConfigError, database_url
import teajoin


LOCAL_MODE = "local"
PUBLIC_MODE = "public"


def deployment_mode() -> str:
    mode = (os.environ.get("VR_DEPLOYMENT_MODE") or LOCAL_MODE).strip().lower()
    if mode not in {LOCAL_MODE, PUBLIC_MODE}:
        raise RuntimeError("VR_DEPLOYMENT_MODE must be local or public")
    return mode


def is_public_mode() -> bool:
    return deployment_mode() == PUBLIC_MODE


def parse_csv_env(name: str) -> tuple[str, ...]:
    return tuple(item.strip().lower().rstrip(".") for item in (os.environ.get(name) or "").split(",") if item.strip())


def ai_allowed_hosts() -> tuple[str, ...]:
    return parse_csv_env("VR_AI_ALLOWED_HOSTS")


def require_secure_cookie() -> None:
    if is_public_mode() and (os.environ.get("VR_COOKIE_SECURE") or "").strip().lower() != "true":
        raise RuntimeError("VR_COOKIE_SECURE=true is required when VR_DEPLOYMENT_MODE=public")


def enforce_startup_policy() -> None:
    if not is_public_mode():
        return
    try:
        database_url()
    except DatabaseConfigError as exc:
        raise RuntimeError("VR_DATABASE_URL must be configured for public mode") from exc
    try:
        teajoin._api_key()
    except teajoin.TeaJoinConfigError as exc:
        raise RuntimeError("TEAJOIN_API_KEY is required for public mode") from exc
    require_secure_cookie()
    origins = parse_csv_env("VR_ALLOW_ORIGINS")
    if not origins or any(not origin.startswith("https://") for origin in origins):
        raise RuntimeError("VR_ALLOW_ORIGINS must contain explicit https origins in public mode")
    if not ai_allowed_hosts():
        raise RuntimeError("VR_AI_ALLOWED_HOSTS is required when VR_DEPLOYMENT_MODE=public")
    if not (os.environ.get("VR_REDIS_URL") or "").strip():
        raise RuntimeError("VR_REDIS_URL is required when VR_DEPLOYMENT_MODE=public")
    scan_command = (os.environ.get("VR_REPORT_SCAN_COMMAND") or "").strip()
    if not scan_command:
        raise RuntimeError("VR_REPORT_SCAN_COMMAND is required when VR_DEPLOYMENT_MODE=public")
    if scan_command.count("{path}") != 1:
        raise RuntimeError("VR_REPORT_SCAN_COMMAND must contain exactly one {path} placeholder")
    if not (os.environ.get("VR_CREDENTIAL_ENCRYPTION_KEY") or "").strip():
        raise RuntimeError("VR_CREDENTIAL_ENCRYPTION_KEY is required when VR_DEPLOYMENT_MODE=public")
    previous_key = (os.environ.get("VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS") or "").strip()
    current_key = (os.environ.get("VR_CREDENTIAL_ENCRYPTION_KEY") or "").strip()
    if previous_key and previous_key == current_key:
        raise RuntimeError("VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS must differ from the current key")
    try:
        redis_client().ping()
    except RedisError as exc:
        raise RuntimeError("VR_REDIS_URL must point to a reachable Redis service in public mode") from exc


@lru_cache(maxsize=1)
def redis_client() -> Redis:
    url = (os.environ.get("VR_REDIS_URL") or "").strip()
    if not url:
        raise RuntimeError("VR_REDIS_URL is not configured")
    return Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)


def redis_ready() -> bool:
    if not is_public_mode():
        return True
    try:
        return bool(redis_client().ping())
    except (RedisError, RuntimeError):
        return False


def enforce_rate_limit(request: Request, scope: str, limit: int, window_seconds: int, user_id: str | None = None) -> None:
    """Apply a fail-closed distributed fixed-window limit in public mode."""
    if not is_public_mode():
        return
    identity = user_id or (request.client.host if request.client else "unknown")
    window = int(time.time() // window_seconds)
    key = f"vr:limit:{scope}:{identity}:{window}"
    try:
        count = redis_client().incr(key)
        if count == 1:
            redis_client().expire(key, window_seconds)
    except (RedisError, RuntimeError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "请求保护服务暂不可用") from exc
    if count > limit:
        retry_after = window_seconds - int(time.time() % window_seconds)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "请求过于频繁，请稍后再试",
            headers={"Retry-After": str(max(1, retry_after))},
        )
