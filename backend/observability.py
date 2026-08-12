"""Safe request correlation and structured HTTP access logging."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from fastapi import Request, Response


_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_LOGGER = logging.getLogger("vibe_research.http")


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
