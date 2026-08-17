"""TeaJoin 的 Tushare 兼容 HTTP 适配器。密钥只从运行环境或本地 .env 读取。"""
from __future__ import annotations

import os
import random
import time
from pathlib import Path
from threading import Lock
from typing import Any

import requests

BASE_URL = "https://teajoin.com"
TIMEOUT_S = 15
MIN_INTERVAL_S = 0.2
MAX_ATTEMPTS = 3
_LAST_REQUEST_AT = 0.0
_RATE_LOCK = Lock()


class TeaJoinError(RuntimeError):
    """TeaJoin 调用的基类异常。"""


class TeaJoinConfigError(TeaJoinError):
    """未提供 TeaJoin 密钥。"""


class TeaJoinUpstreamError(TeaJoinError):
    """TeaJoin 网络、HTTP 或业务响应异常。"""


def _load_dotenv_key() -> str:
    """读取本模块同级、被 .gitignore 排除的最小 .env 文件，不覆盖进程环境。"""
    path = Path(__file__).with_name(".env")
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "TEAJOIN_API_KEY":
                return value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


def _api_key() -> str:
    key = os.environ.get("TEAJOIN_API_KEY", "").strip() or _load_dotenv_key()
    if not key:
        raise TeaJoinConfigError("未配置 TEAJOIN_API_KEY；请在 backend/.env 中设置")
    return key


def _wait_for_rate_limit() -> None:
    global _LAST_REQUEST_AT
    with _RATE_LOCK:
        now = time.monotonic()
        delay = MIN_INTERVAL_S - (now - _LAST_REQUEST_AT)
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST_AT = time.monotonic()


def _post(payload: dict[str, Any]) -> requests.Response:
    """POST with bounded retries for transient network and 5xx failures."""
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        _wait_for_rate_limit()
        try:
            response = requests.post(BASE_URL, json=payload, timeout=TIMEOUT_S)
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code < 500 or attempt == MAX_ATTEMPTS - 1:
                return response
            last_error = TeaJoinUpstreamError(f"TeaJoin HTTP {response.status_code}")
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep((0.35 * (2 ** attempt)) + random.uniform(0, 0.1))
    raise TeaJoinUpstreamError(f"TeaJoin 请求失败：{last_error}") from last_error


def call(api_name: str, params: dict[str, Any] | None = None, fields: str = "") -> list[dict[str, Any]]:
    """调用 TeaJoin，并将 Tushare 的 fields/items 标准响应转为字典列表。"""
    payload: dict[str, Any] = {"api_name": api_name, "token": _api_key(), "params": params or {}}
    if fields:
        payload["fields"] = fields
    try:
        response = _post(payload)
        body = response.json()
    except TeaJoinUpstreamError:
        raise
    except ValueError as exc:
        raise TeaJoinUpstreamError(f"TeaJoin 请求失败：{exc}") from exc
    if response.status_code >= 400:
        detail = body.get("msg") or body.get("message") or response.text
        raise TeaJoinUpstreamError(f"TeaJoin HTTP {response.status_code}：{detail}")
    if not isinstance(body, dict):
        raise TeaJoinUpstreamError("TeaJoin 返回格式无效")
    if body.get("code") not in (None, 0):
        raise TeaJoinUpstreamError(str(body.get("msg") or body.get("message") or "TeaJoin 业务请求失败"))
    data = body.get("data")
    if not isinstance(data, dict):
        raise TeaJoinUpstreamError("TeaJoin 返回缺少 data")
    names, items = data.get("fields"), data.get("items")
    if not isinstance(names, list) or not isinstance(items, list):
        raise TeaJoinUpstreamError("TeaJoin 返回缺少 fields/items")
    return [dict(zip(names, item)) for item in items if isinstance(item, list)]
