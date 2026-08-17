"""TeaJoin-backed, validated index candle series for Daily Review."""
from __future__ import annotations

import math
import threading
import time
from datetime import datetime, time as clock_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import teajoin


class UnknownIndex(ValueError):
    pass


class InvalidIndexData(RuntimeError):
    pass


_INSTRUMENTS: dict[str, dict[str, str]] = {
    "CN.SH.000001": {"vendor_symbol": "000001.SH", "name": "上证指数", "market": "CN", "exchange": "SSE", "currency": "CNY", "timezone": "Asia/Shanghai", "source_api": "index_daily"},
    "CN.SZ.399001": {"vendor_symbol": "399001.SZ", "name": "深证成指", "market": "CN", "exchange": "SZSE", "currency": "CNY", "timezone": "Asia/Shanghai", "source_api": "index_daily"},
    "CN.SZ.399006": {"vendor_symbol": "399006.SZ", "name": "创业板指", "market": "CN", "exchange": "SZSE", "currency": "CNY", "timezone": "Asia/Shanghai", "source_api": "index_daily"},
    "CN.SH.000300": {"vendor_symbol": "000300.SH", "name": "沪深300", "market": "CN", "exchange": "SSE", "currency": "CNY", "timezone": "Asia/Shanghai", "source_api": "index_daily"},
    "GLOBAL.DJI": {"vendor_symbol": "DJI", "name": "道琼斯", "market": "US", "exchange": "NYSE", "currency": "USD", "timezone": "America/New_York", "source_api": "index_global"},
    "GLOBAL.SPX": {"vendor_symbol": "SPX", "name": "标普500", "market": "US", "exchange": "NYSE", "currency": "USD", "timezone": "America/New_York", "source_api": "index_global"},
    "GLOBAL.IXIC": {"vendor_symbol": "IXIC", "name": "纳斯达克", "market": "US", "exchange": "NASDAQ", "currency": "USD", "timezone": "America/New_York", "source_api": "index_global"},
    "GLOBAL.HSI": {"vendor_symbol": "HSI", "name": "恒生指数", "market": "HK", "exchange": "HKEX", "currency": "HKD", "timezone": "Asia/Hong_Kong", "source_api": "index_global"},
    "GLOBAL.HKTECH": {"vendor_symbol": "HKTECH", "name": "恒生科技", "market": "HK", "exchange": "HKEX", "currency": "HKD", "timezone": "Asia/Hong_Kong", "source_api": "index_global"},
}

_FIELDS = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
_CACHE: dict[tuple[str, int, str], tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_HISTORY_TTL_S = 900
_SESSION_CACHE: dict[str, tuple[float, bool]] = {}



def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cn_market_session() -> str:
    now = _utc_now()
    local_date = now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    monotonic_now = time.monotonic()
    with _CACHE_LOCK:
        hit = _SESSION_CACHE.get(local_date)
    if hit and monotonic_now - hit[0] < 3600:
        is_open = hit[1]
    else:
        try:
            rows = teajoin.call("trade_cal", {"exchange": "SSE", "start_date": local_date, "end_date": local_date}, "cal_date,is_open")
            is_open = bool(rows and int(rows[0].get("is_open") or 0) == 1)
        except (teajoin.TeaJoinError, TypeError, ValueError):
            is_open = now.astimezone(ZoneInfo("Asia/Shanghai")).weekday() < 5
        with _CACHE_LOCK:
            _SESSION_CACHE.clear()
            _SESSION_CACHE[local_date] = (monotonic_now, is_open)
    return a_share_session(now, is_open_day=is_open)["state"]


def _global_market_session(instrument: dict[str, str], at: datetime) -> str:
    """Exchange-local session state for the indices shown as global context."""
    local = at.astimezone(ZoneInfo(instrument["timezone"]))
    if local.weekday() >= 5:
        return "closed_day"
    current = local.time()
    if instrument["market"] == "US":
        if current < clock_time(9, 30):
            return "pre_open"
        return "trading" if current <= clock_time(16, 0) else "closed"
    # HKEX continuous session. Public quote timestamps remain the authority on
    # whether a same-day quote can be overlaid; this only controls refresh.
    if current < clock_time(9, 30):
        return "pre_open"
    if current <= clock_time(12, 0):
        return "trading"
    if current < clock_time(13, 0):
        return "lunch_break"
    return "trading" if current <= clock_time(16, 0) else "closed"


def _number(value: Any, field: str) -> float:
    if value is None or isinstance(value, bool):
        raise InvalidIndexData(f"missing {field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidIndexData(f"invalid {field}") from exc
    if not math.isfinite(number):
        raise InvalidIndexData(f"invalid {field}")
    return number


def _optional_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    raw_date = str(row.get("trade_date") or "")
    try:
        trade_date = datetime.strptime(raw_date, "%Y%m%d").date().isoformat()
    except ValueError as exc:
        raise InvalidIndexData("invalid trade_date") from exc
    open_, high, low, close = (_number(row.get(key), key) for key in ("open", "high", "low", "close"))
    if low > min(open_, close) or high < max(open_, close) or low > high:
        raise InvalidIndexData("invalid OHLC relationship")
    return {
        "trade_date": trade_date,
        "open": open_, "high": high, "low": low, "close": close,
        "pre_close": _optional_number(row.get("pre_close")),
        "change": _optional_number(row.get("change")),
        "pct_chg": _optional_number(row.get("pct_chg")),
        "volume": _optional_number(row.get("vol")),
        # TeaJoin/Tushare index_daily reports amount in thousand CNY; the
        # front-end contract is always CNY, matching live quote amounts.
        "amount": (_optional_number(row.get("amount")) * 1_000) if _optional_number(row.get("amount")) is not None else None,
        "is_partial": False,
    }


def a_share_session(at: datetime, *, is_open_day: bool) -> dict[str, Any]:
    local = at.astimezone(ZoneInfo("Asia/Shanghai"))
    if not is_open_day:
        return {"state": "closed_day", "should_poll": False}
    current = local.time()
    if current < clock_time(9, 30):
        return {"state": "pre_open", "should_poll": False}
    if current <= clock_time(11, 30):
        return {"state": "trading", "should_poll": True}
    if current < clock_time(13, 0):
        return {"state": "lunch_break", "should_poll": False}
    if current <= clock_time(15, 0):
        return {"state": "trading", "should_poll": True}
    return {"state": "closed", "should_poll": False}


def _date_range(limit: int) -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    return (today - timedelta(days=max(limit * 2, 120))).strftime("%Y%m%d"), today.strftime("%Y%m%d")


def _series_status(candles: list[dict[str, Any]], local_today: str) -> tuple[str, str | None]:
    if not candles:
        return "source_unavailable", "no_teajoin_candle"
    if candles[-1]["trade_date"] == local_today:
        return "fresh", None
    return "historical", "previous_trade_day"


def get_index_series(symbol: str, period: str = "1d", limit: int = 60, *, use_cache: bool = True) -> dict[str, Any]:
    if period != "1d":
        raise ValueError("only period=1d is supported")
    instrument = _INSTRUMENTS.get(symbol)
    if instrument is None:
        raise UnknownIndex(symbol)
    now = time.monotonic()
    now_at = _utc_now()
    session = _cn_market_session() if instrument["market"] == "CN" else _global_market_session(instrument, now_at)
    # Keep cache entries scoped to the exchange session. In particular, an
    # intraday snapshot must never be reused after the closing boundary.
    key = (symbol, limit, session)
    cache_ttl = _HISTORY_TTL_S
    if use_cache:
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
            if hit and now - hit[0] < cache_ttl:
                return hit[1]
    start_date, end_date = _date_range(limit)
    rows = teajoin.call(instrument["source_api"], {
        "ts_code": instrument["vendor_symbol"], "start_date": start_date, "end_date": end_date,
    }, _FIELDS)
    candles = [_normalize_row(row) for row in rows]
    candles.sort(key=lambda row: row["trade_date"])
    dates = [row["trade_date"] for row in candles]
    if len(dates) != len(set(dates)):
        raise InvalidIndexData("duplicate trade_date")
    candles = candles[-1:]
    local_today = now_at.astimezone(ZoneInfo(instrument["timezone"])).date().isoformat()
    data_status, status_reason = _series_status(candles, local_today)
    retrieved_at = now_at.isoformat()
    result = {
        "symbol": symbol, **instrument,
        "frequency": "1d", "adjustment": "none",
        "volume_unit": None, "amount_unit": instrument["currency"],
        "source": "TeaJoin",
        "source_api": instrument["source_api"],
        "retrieved_at": retrieved_at,
        "as_of": candles[-1]["trade_date"] if candles else None,
        "data_status": data_status,
        "market_session": session,
        "realtime_available": False,
        "quote_at": None,
        "status_reason": status_reason,
        "candles": candles,
    }
    if candles and use_cache:
        with _CACHE_LOCK:
            _CACHE[key] = (now, result)
    return result


def get_index_series_batch(symbols: list[str], period: str = "1d", limit: int = 60) -> list[dict[str, Any]]:
    return [get_index_series(symbol, period=period, limit=limit) for symbol in symbols]
