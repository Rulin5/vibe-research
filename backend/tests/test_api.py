"""API 验证/契约测（FastAPI TestClient）。大多在校验层就返回，不联网、可靠。"""
import pytest
from fastapi.testclient import TestClient

import app as app_module
import index_market

client = TestClient(app_module.app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_index_candles_batch_contract(monkeypatch):
    monkeypatch.setattr(app_module, "_public_datasets", lambda: {
        "index_candles": [
            {"symbol": "CN.SH.000001", "frequency": "1d", "candles": [{"close": 1}]},
            {"symbol": "GLOBAL.SPX", "frequency": "1d", "candles": [{"close": 2}]},
        ],
    })
    response = client.get("/api/market/index-candles?symbols=CN.SH.000001,GLOBAL.SPX&period=1d&limit=60")
    assert response.status_code == 200
    assert [row["symbol"] for row in response.json()["data"]] == ["CN.SH.000001", "GLOBAL.SPX"]
    assert response.json()["data"][0]["candles"][-1]["close"] == 1


def test_index_candles_rejects_unknown_symbol(monkeypatch):
    monkeypatch.setattr(app_module, "_public_datasets", lambda: {"index_candles": []})
    assert client.get("/api/market/index-candles?symbols=UNKNOWN").status_code == 422


def test_dashboard_uses_published_snapshot_without_calling_live_source(monkeypatch):
    monkeypatch.setattr(app_module, "_public_datasets", lambda: {"indices": [{"name": "snapshot"}]})
    monkeypatch.setattr(app_module.astock, "index_quote", lambda: (_ for _ in ()).throw(AssertionError("must not call live source")))

    response = client.get("/api/indices")

    assert response.status_code == 200
    assert response.json()["data"] == [{"name": "snapshot"}]


def test_dashboard_requires_a_published_snapshot(monkeypatch):
    monkeypatch.setattr(app_module._PUBLIC_DATA_REFRESH.store, "load_current", lambda: None)

    response = client.get("/api/indices")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "public_data_snapshot_not_ready"


@pytest.mark.parametrize("query", [
    "symbols=CN.SH.000001&limit=0",
    "symbols=CN.SH.000001&limit=251",
    "symbols=CN.SH.000001&period=5m",
    "symbols=CN.SH.000001,CN.SH.000001",
])
def test_index_candles_validates_query(query):
    assert client.get(f"/api/market/index-candles?{query}").status_code == 422


@pytest.mark.parametrize("path", [
    "/api/quote?codes=abc",
    "/api/valuation?code=12",
    "/api/margin?code=notcode",
    "/api/holders?code=1234567",
    "/api/announcements?code=",
])
def test_bad_code_400(path):
    assert client.get(path).status_code == 400


def test_industry_top_range():
    assert client.get("/api/industry?top=2").status_code == 422   # ge=5
    assert client.get("/api/industry?top=999").status_code == 422  # le=50


def test_chat_empty_messages_400(authenticated_client):
    private_client, headers = authenticated_client
    r = private_client.post("/api/chat", json={"messages": []}, headers=headers)
    assert r.status_code == 422


def test_chat_api_missing_key_400(authenticated_client, monkeypatch):
    private_client, headers = authenticated_client
    monkeypatch.delenv("VR_AI_STEPFUN_API_KEY", raising=False)
    # API 接入缺 baseURL/apiKey → 400（在开流前拦下）
    r = private_client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "hi"}],
        "llm": {"provider": "deepseek", "model": "deepseek-chat", "baseURL": "", "apiKey": ""},
    }, headers=headers)
    assert r.status_code == 422


def test_chat_cli_not_installed_400(authenticated_client, monkeypatch):
    private_client, headers = authenticated_client
    monkeypatch.delenv("VR_AI_STEPFUN_API_KEY", raising=False)
    # 订阅接入选一个本机没装的 CLI → 400 明确提示（不静默失败）
    r = private_client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "hi"}],
        "llm": {"provider": "cli-qwen", "model": "qwen-code", "baseURL": "", "apiKey": ""},
    }, headers=headers)
    # qwen 一般未装 → 400；若恰好装了 qwen 则会进流式（放宽断言）
    assert r.status_code == 422


def test_global_stock_404(monkeypatch):
    """无法解析的美股/港股代码 → 404（不 500、不崩）。"""
    import gstock
    monkeypatch.setattr(gstock, "us_hk_stock", lambda q: {})
    assert client.get("/api/global/stock?symbol=ZZZZ").status_code == 404


def test_gstock_quote_full_null_shape():
    """行情取不到时 `_quote_from({})` 仍返回完整 null 形状（契合 GlobalQuote 类型），不是空 dict。"""
    import gstock
    q = gstock._quote_from({})
    assert set(q) == {"code", "name", "price", "open", "high", "low", "prev_close", "amount", "mcap", "change_pct"}
    assert all(v is None for v in q.values())


def test_sector_members_returns_normalized_constituents(monkeypatch):
    snapshot = {"snapshot_id": "snapshot-1", "status": "completed", "as_of": "20260811", "sectors": [
        {"kind": "概念", "code": "882001.TI", "data_status": "complete"},
    ]}
    monkeypatch.setattr(app_module._SECTOR_REFRESH.store, "load_current", lambda: snapshot)
    monkeypatch.setattr(app_module._SECTOR_REFRESH.store, "load_members", lambda *args: [{
        "code": "600519", "name": "贵州茅台", "market": "主板", "joined_at": "20200101",
    }])
    r = client.get("/api/sector-members?kind=%E6%A6%82%E5%BF%B5&code=882001.TI")
    assert r.status_code == 200
    assert r.json()["data"]["source"] == "TeaJoin/Tushare ths_member verified snapshot"
    assert r.json()["data"]["snapshot_id"] == "snapshot-1"
    assert r.json()["data"]["members"][0]["code"] == "600519"


def test_sector_members_invalid_kind_code_returns_404(monkeypatch):
    snapshot = {"snapshot_id": "snapshot-1", "status": "completed", "as_of": "20260811", "sectors": [
        {"kind": "行业", "code": "881001.TI", "data_status": "complete"},
    ]}
    monkeypatch.setattr(app_module._SECTOR_REFRESH.store, "load_current", lambda: snapshot)
    r = client.get("/api/sector-members?kind=%E6%A6%82%E5%BF%B5&code=881001.TI")
    assert r.status_code == 404


def test_sector_endpoints_read_one_verified_snapshot(monkeypatch):
    snapshot = {
        "snapshot_id": "20260811-v1", "status": "completed", "as_of": "20260811",
        "retrieved_at": "2026-08-11T16:00:00+08:00", "source": "TeaJoin/Tushare",
        "market": "CN-A", "currency": "CNY", "timezone": "Asia/Shanghai", "frequency": "1d",
        "method_version": "test", "completeness": {"candidate_count": 2, "published_count": 2, "excluded_count": 0},
        "sectors": [
            {"kind": "行业", "code": "881101.TI", "name": "种植业与林业", "as_of": "20260811", "close": 1.0,
             "pct_change": 1.0, "member_count": 1, "lead_stock": "示例股", "net_amount": 1.0, "data_status": "complete"},
            {"kind": "概念", "code": "885001.TI", "name": "人工智能", "as_of": "20260811", "close": 1.0,
             "pct_change": -1.0, "member_count": 1, "lead_stock": "示例股", "net_amount": 1.0, "data_status": "complete"},
        ],
    }
    monkeypatch.setattr(app_module._SECTOR_REFRESH.store, "load_current", lambda: snapshot)
    monkeypatch.setattr(
        app_module._SECTOR_REFRESH.store,
        "load_members",
        lambda snapshot_id, kind, code: [{"code": "600000", "name": "浦发银行", "market": "A股", "joined_at": ""}],
    )

    sectors = client.get("/api/all-sectors")
    detail = client.get("/api/sector-detail?kind=%E8%A1%8C%E4%B8%9A&code=881101.TI")
    members = client.get("/api/sector-members?kind=%E8%A1%8C%E4%B8%9A&code=881101.TI")

    assert sectors.status_code == detail.status_code == members.status_code == 200
    assert sectors.json()["data"]["snapshot_id"] == "20260811-v1"
    assert detail.json()["data"]["snapshot_id"] == "20260811-v1"
    assert members.json()["data"]["snapshot_id"] == "20260811-v1"
    assert members.json()["data"]["members"]


def test_stock_search_matches_code_or_name(monkeypatch):
    import astock

    monkeypatch.setattr(astock, "teajoin_stock_search", lambda query, limit: [{
        "code": "600519", "ts_code": "600519.SH", "name": "贵州茅台", "market": "主板", "industry": "白酒",
    }])
    r = client.get("/api/stocks/search?query=%E8%8C%85%E5%8F%B0")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["query"] == "茅台"
    assert body["results"][0]["ts_code"] == "600519.SH"


def test_stock_search_rejects_unsafe_short_queries():
    assert client.get("/api/stocks/search?query=a").status_code == 422


def test_sector_reads_keep_serving_complete_stale_snapshot(monkeypatch):
    snapshot = {
        "snapshot_id": "stale-v1", "status": "completed", "as_of": "20260801",
        "retrieved_at": "2026-08-01T15:00:00+08:00", "source": "TeaJoin/Tushare",
        "market": "CN-A", "currency": "CNY", "timezone": "Asia/Shanghai", "frequency": "1d",
        "method_version": "test", "completeness": {"candidate_count": 1, "published_count": 1, "excluded_count": 0},
        "sectors": [{
            "kind": "行业", "code": "881101.TI", "name": "种植业与林业", "as_of": "20260801",
            "close": 1.0, "pct_change": 1.0, "member_count": 1, "lead_stock": "示例股",
            "net_amount": 1.0, "data_status": "complete",
        }],
    }
    monkeypatch.setattr(app_module._SECTOR_REFRESH, "readiness", lambda: {"ok": True, "stale": True, "age_seconds": 600})
    monkeypatch.setattr(app_module._SECTOR_REFRESH.store, "load_current", lambda: snapshot)

    response = client.get("/api/all-sectors")

    assert response.status_code == 200
    assert response.json()["data"]["industries"]
    assert response.json()["data"]["stale"] is True


def test_sector_refresh_requires_authenticated_csrf_protected_request():
    assert client.post("/api/sectors/refresh").status_code == 401


def test_sector_refresh_is_user_rate_limited(authenticated_client, monkeypatch):
    private_client, headers = authenticated_client
    seen = {}
    monkeypatch.setattr(app_module, "enforce_rate_limit", lambda request, scope, limit, window_seconds, user_id=None: seen.update({"scope": scope, "limit": limit, "user_id": user_id}))
    monkeypatch.setattr(app_module._SECTOR_REFRESH, "start", lambda request_id: {"request_id": request_id, "status": "pending"})

    response = private_client.post("/api/sectors/refresh", headers=headers)

    assert response.status_code == 202
    assert seen["scope"] == "sector-refresh"
    assert seen["limit"] == 1
    assert seen["user_id"]


def test_sector_master_data_uses_only_ths_industry_and_concept_types(monkeypatch):
    import astock

    astock._TEAJOIN_SECTORS = None

    def fake_call(api_name, params=None, fields=""):
        if api_name == "trade_cal":
            return [{"cal_date": "20260811", "is_open": 1}]
        if api_name == "moneyflow_ind_ths":
            return [{"ts_code": "881001.TI", "industry": "能源", "pct_change": 0.1, "company_num": 20}]
        if api_name == "ths_index":
            return [
                {"ts_code": "881001.TI", "name": "能源", "type": "I", "exchange": "A", "count": 20},
                {"ts_code": "885001.TI", "name": "人工智能", "type": "N", "exchange": "A", "count": 30},
                {"ts_code": "865067.TI", "name": "无可用成分", "type": "N", "exchange": "A", "count": 1},
                {"ts_code": "700001.TI", "name": "同花顺全A", "type": "BB", "exchange": "A", "count": 5000},
            ]
        raise AssertionError(f"unexpected api: {api_name}")

    monkeypatch.setattr(astock.teajoin, "call", fake_call)
    data = astock.teajoin_all_sectors()
    assert data["source"] == "TeaJoin/Tushare moneyflow_ind_ths + ths_index"
    assert [row["code"] for row in data["industries"]] == ["881001.TI"]
    assert [row["code"] for row in data["concepts"]] == ["885001.TI"]
    assert data["concepts"][0]["change_pct"] is None


def test_sector_master_uses_latest_industry_daily_data_without_mixing_concepts(monkeypatch):
    import astock

    astock._TEAJOIN_SECTORS = None

    def fake_call(api_name, params=None, fields=""):
        if api_name == "trade_cal":
            return [
                {"cal_date": "20260811", "is_open": 1},
                {"cal_date": "20260810", "is_open": 1},
            ]
        if api_name == "moneyflow_ind_ths":
            if params["trade_date"] == "20260811":
                return [{
                    "trade_date": "20260811", "ts_code": "881001.TI", "industry": "能源",
                    "pct_change": 1.25, "company_num": 36, "lead_stock": "示例股份",
                    "net_amount": 123456.0,
                }]
            return []
        if api_name == "ths_index":
            return [{"ts_code": "885001.TI", "name": "人工智能", "type": "N", "count": 30}]
        raise AssertionError(f"unexpected api: {api_name}")

    monkeypatch.setattr(astock.teajoin, "call", fake_call)
    data = astock.teajoin_all_sectors()

    assert data["as_of"] == "20260811"
    assert data["source"] == "TeaJoin/Tushare moneyflow_ind_ths + ths_index"
    assert data["industries"] == [{
        "code": "881001.TI", "name": "能源", "kind": "行业", "member_count": 36,
        "change_pct": 1.25, "up_count": None, "down_count": None,
        "lead_stock": "示例股份", "net_amount": 123456.0, "as_of": "20260811",
    }]
    assert data["concepts"][0]["code"] == "885001.TI"
    assert data["concepts"][0]["change_pct"] is None


def test_sector_master_falls_back_to_previous_open_day_when_today_has_no_industry_rows(monkeypatch):
    import astock

    astock._TEAJOIN_SECTORS = None
    requested_dates = []

    def fake_call(api_name, params=None, fields=""):
        if api_name == "trade_cal":
            return [{"cal_date": "20260811", "is_open": 1}, {"cal_date": "20260810", "is_open": 1}]
        if api_name == "moneyflow_ind_ths":
            requested_dates.append(params["trade_date"])
            return [] if params["trade_date"] == "20260811" else [{
                "trade_date": "20260810", "ts_code": "881001.TI", "industry": "能源",
                "pct_change": -0.66, "company_num": 36,
            }]
        if api_name == "ths_index":
            return []
        raise AssertionError(f"unexpected api: {api_name}")

    monkeypatch.setattr(astock.teajoin, "call", fake_call)
    data = astock.teajoin_all_sectors()

    assert requested_dates == ["20260811", "20260810"]
    assert data["as_of"] == "20260810"
    assert data["industries"][0]["change_pct"] == -0.66


def test_sector_members_rejects_code_outside_its_declared_kind(monkeypatch):
    import astock

    monkeypatch.setattr(astock, "teajoin_all_sectors", lambda: {
        "industries": [{"code": "881001.TI", "name": "能源", "kind": "行业"}],
        "concepts": [], "source": "TeaJoin/Tushare ths_index", "as_of": None,
    })
    with pytest.raises(ValueError, match="板块代码与分类不匹配"):
        astock.teajoin_sector_members("概念", "881001.TI")
