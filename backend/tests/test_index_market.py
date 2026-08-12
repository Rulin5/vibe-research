from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import index_market


def test_history_is_normalized_oldest_first(monkeypatch):
    monkeypatch.setattr(index_market.teajoin, "call", lambda *args, **kwargs: [
        {"ts_code": "000001.SH", "trade_date": "20260811", "open": 3650, "high": 3690, "low": 3640, "close": 3680, "vol": 100, "amount": 200},
        {"ts_code": "000001.SH", "trade_date": "20260808", "open": 3600, "high": 3660, "low": 3590, "close": 3650, "vol": 90, "amount": 180},
    ])

    series = index_market.get_index_series("CN.SH.000001", limit=60, use_cache=False)

    assert [row["trade_date"] for row in series["candles"]] == ["2026-08-08", "2026-08-11"]
    assert series["source_api"] == "index_daily"
    assert series["candles"][-1]["is_partial"] is False


def test_global_symbol_uses_index_global(monkeypatch):
    seen = {}

    def fake_call(api_name, params, fields):
        seen.update(api_name=api_name, params=params, fields=fields)
        return [{"ts_code": "HKTECH", "trade_date": "20260811", "open": 5500, "high": 5600, "low": 5480, "close": 5570, "vol": 12}]

    monkeypatch.setattr(index_market.teajoin, "call", fake_call)
    series = index_market.get_index_series("GLOBAL.HKTECH", limit=60, use_cache=False)

    assert seen["api_name"] == "index_global"
    assert seen["params"]["ts_code"] == "HKTECH"
    assert series["currency"] == "HKD"


@pytest.mark.parametrize("row", [
    {"trade_date": "20260811", "open": None, "high": 10, "low": 8, "close": 9},
    {"trade_date": "20260811", "open": 9, "high": 8, "low": 7, "close": 10},
])
def test_invalid_ohlc_is_rejected(monkeypatch, row):
    monkeypatch.setattr(index_market.teajoin, "call", lambda *args, **kwargs: [row])
    with pytest.raises(index_market.InvalidIndexData):
        index_market.get_index_series("CN.SH.000001", use_cache=False)


def test_duplicate_trade_date_is_rejected(monkeypatch):
    row = {"trade_date": "20260811", "open": 9, "high": 10, "low": 8, "close": 9.5}
    monkeypatch.setattr(index_market.teajoin, "call", lambda *args, **kwargs: [row, dict(row)])
    with pytest.raises(index_market.InvalidIndexData, match="duplicate"):
        index_market.get_index_series("CN.SH.000001", use_cache=False)


@pytest.mark.parametrize(("at", "expected", "poll"), [
    ("2026-08-12T09:29:59+08:00", "pre_open", False),
    ("2026-08-12T09:30:00+08:00", "trading", True),
    ("2026-08-12T11:30:01+08:00", "lunch_break", False),
    ("2026-08-12T13:00:00+08:00", "trading", True),
    ("2026-08-12T15:00:01+08:00", "closed", False),
])
def test_a_share_session_boundaries(at, expected, poll):
    state = index_market.a_share_session(datetime.fromisoformat(at), is_open_day=True)
    assert state == {"state": expected, "should_poll": poll}


def test_non_trading_day_never_polls():
    at = datetime(2026, 8, 15, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert index_market.a_share_session(at, is_open_day=False) == {"state": "closed_day", "should_poll": False}


def test_cn_series_uses_trade_calendar_for_session(monkeypatch):
    index_market._SESSION_CACHE.clear()
    def fake_call(api_name, params, fields=""):
        if api_name == "trade_cal":
            return [{"cal_date": "20260812", "is_open": 0}]
        return [{"trade_date": "20260811", "open": 9, "high": 10, "low": 8, "close": 9.5}]

    monkeypatch.setattr(index_market.teajoin, "call", fake_call)
    monkeypatch.setattr(index_market, "_utc_now", lambda: datetime.fromisoformat("2026-08-12T10:00:00+08:00"))
    series = index_market.get_index_series("CN.SH.000001", use_cache=False)
    assert series["market_session"] == "closed_day"
