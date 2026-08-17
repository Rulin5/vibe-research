"""Safe request correlation and structured HTTP access logging."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from fastapi import Request, Response
from sqlalchemy.exc import SQLAlchemyError


_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_LOGGER = logging.getLogger("vibe_research.http")
_ERROR_LOGGER = logging.getLogger("vibe_research.error")


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "")
    return supplied if _SAFE_REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())


async def request_observability_middleware(request: Request, call_next) -> Response:
    request_id = _request_id(request)
    request.state.request_id = request_id
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        _LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "user_fingerprint": getattr(request.state, "user_fingerprint", None),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )


async def dependency_error_middleware(request: Request, call_next) -> Response:
    """Expose expected infrastructure failures as retryable, traceable API responses."""
    try:
        return await call_next(request)
    except SQLAlchemyError:
        _ERROR_LOGGER.exception(
            "database_dependency_failure request_id=%s method=%s path=%s",
            getattr(request.state, "request_id", None),
            request.method,
            request.url.path,
        )
        return Response(
            content='{"detail":"数据库服务暂不可用"}',
            status_code=503,
            media_type="application/json",
            headers={"X-Request-ID": getattr(request.state, "request_id", "")},
        )
    except Exception:
        _ERROR_LOGGER.exception(
            "unhandled_request_failure request_id=%s method=%s path=%s",
            getattr(request.state, "request_id", None),
            request.method,
            request.url.path,
        )
        raise
