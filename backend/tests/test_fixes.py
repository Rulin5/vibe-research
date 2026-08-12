"""审计修复回归测（2026-07-05，全部离线）：
免登录 API / 持仓 CRUD 与坏文件降级 / 估值脏数据防护 / 涨停池脏数值 /
空结果不缓存 / akshare 缺失降级 / 无 index 工具调用归位 / CLI 流式超时。
"""
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app as app_module
import astock
import chat
import cli_runtime
import market
import portfolio as pf
from db import get_session
from models import User

ORIGIN = "http://127.0.0.1:5900"


@pytest.fixture()
def private_client():
    username = f"fix_{uuid4().hex[:16]}"
    client = TestClient(app_module.app)
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "CorrectHorseBatteryStaple!9", "phone": "19198273569"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201
    try:
        yield client
    finally:
        session = next(get_session())
        try:
            user = session.query(User).filter(User.username == username).one_or_none()
            if user is not None:
                session.delete(user)
                session.commit()
        finally:
            session.close()


def _write_headers(client: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies.get("vr_csrf", "")}


# ── API 不要求登录或访问密钥 ────────────────────────────────────────

def test_api_routes_ignore_legacy_access_key(monkeypatch):
    # 旧部署环境即使残留访问密钥配置，也不能使数据接口回退到 401。
    monkeypatch.setattr(app_module, "_legacy_access_key", "sekret", raising=False)
    response = TestClient(app_module.app).get("/api/quote?codes=abc")
    # 请求直接进入参数校验层；无 Authorization 请求头同样可访问。
    assert response.status_code == 400


# ── 持仓：本地 JSON CRUD（不联网，行情打桩） ────────────────────────

@pytest.fixture()
def tmp_pf(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(pf, "PF_FILE", str(tmp_path / "portfolio.json"))
    monkeypatch.setattr(astock, "tencent_quote", lambda codes: {c: {"name": f"股{c}", "price": 10.0} for c in codes})
    return tmp_path


def test_portfolio_crud_roundtrip(tmp_pf, private_client):
    client, headers = private_client, _write_headers(private_client)
    assert client.get("/api/portfolio").json()["data"]["holdings"] == []
    assert client.post("/api/portfolio/holding", json={"code": "600519", "shares": 100, "cost": 8.0}, headers=headers).status_code == 201
    assert client.post("/api/portfolio/holding", json={"code": "600519", "shares": 100, "cost": 12.0}, headers=headers).status_code == 201
    data = client.get("/api/portfolio").json()["data"]
    assert len(data["holdings"]) == 2
    assert sorted(item["cost"] for item in data["holdings"]) == [8.0, 12.0]
    assert all(item["pnl"] == pytest.approx((10.0 - item["cost"]) * item["shares"]) for item in data["holdings"])
    closed = client.post("/api/portfolio/close", json={"code": "600519", "date": "2026-07-05", "price": 11.0, "shares": 200, "cost": 10.0}, headers=headers)
    assert closed.status_code == 201
    assert closed.json()["data"]["pnl"] == pytest.approx(200.0)
    for holding in data["holdings"]:
        assert client.delete(f"/api/portfolio/holding/{holding['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/portfolio/close/{closed.json()['data']['id']}", headers=headers).status_code == 204


def test_portfolio_add_validation(private_client):
    headers = _write_headers(private_client)
    assert private_client.post("/api/portfolio/holding", json={"code": "abc", "shares": 1, "cost": 1}, headers=headers).status_code == 422
    assert private_client.post("/api/portfolio/holding", json={"code": "600519", "shares": 0, "cost": 1}, headers=headers).status_code == 422


def test_portfolio_new_users_start_empty(private_client):
    r = private_client.get("/api/portfolio")
    assert r.status_code == 200
    assert r.json()["data"]["holdings"] == []


# ── issue #13：加仓合并成本保留 4 位小数（ETF/基金成本常见 3-4 位） ──

def test_portfolio_lots_keep_4_decimal_costs(private_client):
    headers = _write_headers(private_client)
    private_client.post("/api/portfolio/holding", json={"code": "510300", "shares": 100, "cost": 1.0001}, headers=headers)
    private_client.post("/api/portfolio/holding", json={"code": "510300", "shares": 100, "cost": 1.0003}, headers=headers)
    holdings = private_client.get("/api/portfolio").json()["data"]["holdings"]
    assert sorted(item["cost"] for item in holdings) == pytest.approx([1.0001, 1.0003], abs=1e-9)


# ── issue #12：旧版数据在仓库内 .cache/，重下载会丢 → 自动迁到用户目录 ──

def test_portfolio_legacy_migration(tmp_path, monkeypatch):
    old = tmp_path / "repo-cache" / "portfolio.json"
    old.parent.mkdir()
    old.write_text('{"holdings": [{"code": "600519", "shares": 100, "cost": 8.0}]}', encoding="utf-8")
    monkeypatch.setattr(pf, "_OLD_PF_FILE", str(old))
    monkeypatch.setattr(pf, "CACHE_DIR", str(tmp_path / "userdata"))
    monkeypatch.setattr(pf, "PF_FILE", str(tmp_path / "userdata" / "portfolio.json"))
    pf._migrate_legacy()
    assert pf._load()["holdings"][0]["code"] == "600519"
    # 新位置已有数据 → 再跑迁移不覆盖
    pf._save({"holdings": []})
    pf._migrate_legacy()
    assert pf._load()["holdings"] == []


def test_myreports_legacy_migration(tmp_path, monkeypatch):
    import myreports as mr

    old = tmp_path / "repo-cache" / "myreports"
    old.mkdir(parents=True)
    (old / "index.json").write_text("[]", encoding="utf-8")
    monkeypatch.delenv("VR_REPORTS_DIR", raising=False)
    monkeypatch.setattr(mr, "_OLD_DEFAULT_DIR", old)
    monkeypatch.setattr(mr, "REPORTS_DIR", tmp_path / "userdata" / "myreports")
    # 上次复制中断留下的半截临时目录，不该挡住这次迁移
    stale = tmp_path / "userdata" / "myreports.migrate.tmp"
    stale.mkdir(parents=True)
    (stale / "partial.bin").write_text("x", encoding="utf-8")
    mr._migrate_legacy()
    dst = tmp_path / "userdata" / "myreports"
    assert (dst / "index.json").exists()
    assert not (dst / "partial.bin").exists()  # 半截内容没混进正式目录


# ── full_valuation：一致预期缺「均值」/ '-' 占位不再 502 ─────────────

_QUOTE = {"600519": {"name": "贵州茅台", "price": 100.0, "mcap_yi": 1000, "pe_ttm": 20.0, "pb": 5.0}}


def test_full_valuation_dirty_forecast(monkeypatch):
    monkeypatch.setattr(astock, "tencent_quote", lambda codes: _QUOTE)
    monkeypatch.setattr(astock, "profit_forecast", lambda code: [
        {"年度": "2026", "预测机构数": "-"},  # 缺「均值」+ 脏机构数
        {"年度": "2027", "均值": "-"},        # '-' 占位
    ])
    out = astock.full_valuation("600519")
    assert out["eps_26e"] is None
    assert out["eps_27e"] is None
    assert out["pe_26e"] is None


def test_full_valuation_string_numbers(monkeypatch):
    monkeypatch.setattr(astock, "tencent_quote", lambda codes: _QUOTE)
    monkeypatch.setattr(astock, "profit_forecast", lambda code: [
        {"年度": "2026年", "均值": "2.0", "预测机构数": "12"},
        {"年度": "2027年", "均值": 2.4},
    ])
    out = astock.full_valuation("600519")
    assert out["eps_26e"] == 2.0
    assert out["analyst_count"] == 12
    assert out["pe_26e"] == 50.0


# ── 短线情绪：涨停池脏数值（'-' 占位）不再让排序崩溃 ────────────────

def test_emotion_dirty_amount(monkeypatch):
    pools = {
        "getTopicZTPool": [
            {"c": "600001", "n": "甲", "lbc": 3, "p": 10000, "zdp": 10.0, "amount": "-", "ltsz": None, "hybk": "X"},
            {"c": "600002", "n": "乙", "lbc": 2, "p": "-", "zdp": None, "amount": 5e8, "ltsz": 1e9, "hybk": "Y"},
        ],
        "getTopicZBPool": [],
        "getTopicDTPool": [],
        "getYesterdayZTPool": [{}],
    }
    monkeypatch.setattr(astock, "em_zt_topic_pool", lambda ep, d, sort="": pools.get(ep, []))
    out = market._emotion()
    stocks = out["lianban_stocks"]
    assert [s["code"] for s in stocks] == ["600001", "600002"]  # 排序没崩、按连板数降序
    assert stocks[0]["amount"] is None    # '-' 归一为 None
    assert stocks[1]["price"] == 0.0      # p='-' 归一后按 0 展示
    assert stocks[1]["amount"] == 5e8


# ── 缓存：数据源故障的空结果不缓存 5 分钟 ───────────────────────────

def test_cached_skips_empty():
    market._CACHE.pop("k_test", None)


def test_market_cache_collapses_concurrent_builds():
    import threading
    import time

    market._CACHE.pop("concurrent_test", None)
    calls = 0
    barrier = threading.Barrier(3)
    results = []

    def expensive():
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return {"ok": 1}

    def worker():
        barrier.wait()
        results.append(market._cached("concurrent_test", expensive))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert results == [{"ok": 1}, {"ok": 1}]
    assert calls == 1
    market._CACHE.pop("concurrent_test", None)
    calls = []

    def flaky():
        calls.append(1)
        return {} if len(calls) == 1 else {"ok": 1}

    assert market._cached("k_test", flaky) == {}
    assert market._cached("k_test", flaky) == {"ok": 1}  # 空结果没被缓存 → 下次重试成功
    assert market._cached("k_test", flaky) == {"ok": 1}  # 非空已缓存，不再调用
    assert len(calls) == 2
    market._CACHE.pop("k_test", None)


# ── akshare 未安装：market 降级返回空，不挡服务 ─────────────────────

def test_market_degrades_without_akshare(monkeypatch):
    def boom():
        raise astock.DependencyMissing("akshare 未安装")

    monkeypatch.setattr(astock, "_akshare", boom)
    assert market._sentiment() == {}
    assert market._sectors() == []


# ── 流式工具调用：非标网关不带 index 时按 id 归位、不串参数 ──────────

def test_stream_tool_calls_without_index(monkeypatch):
    deltas_rounds = [
        [  # 第一轮：增量全部不带 index —— 续块无 id、新调用带新 id
            {"tool_calls": [{"id": "call_a", "function": {"name": "query_quote", "arguments": '{"codes":'}}]},
            {"tool_calls": [{"function": {"arguments": '["600519"]}'}}]},
            {"tool_calls": [{"id": "call_b", "function": {"name": "query_news", "arguments": '{"code":"600519"}'}}]},
        ],
        [{"content": "答案"}],  # 第二轮：纯文本收尾
    ]
    state = {"round": 0}
    monkeypatch.setattr(chat, "_call_llm_stream", lambda cfg, messages, use_tools: None)

    def fake_iter(_resp):
        i = state["round"]
        state["round"] += 1
        yield from deltas_rounds[i]

    monkeypatch.setattr(chat, "_iter_sse_deltas", fake_iter)
    executed = []
    monkeypatch.setattr(chat, "_exec_tool", lambda name, args: (executed.append((name, args)), {"ok": 1})[1])

    events = list(chat.run_chat_stream(
        {"baseURL": "http://x", "apiKey": "k", "model": "m"},
        [{"role": "user", "content": "q"}],
    ))
    assert ("query_quote", {"codes": ["600519"]}) in executed  # 参数没被串坏
    assert ("query_news", {"code": "600519"}) in executed      # 两个调用各归各槽
    assert events[-1]["type"] == "done"


# ── CLI 流式：子进程挂起时超时真正生效（不再无限期阻塞） ────────────

def test_run_cli_stream_timeout(monkeypatch):
    monkeypatch.setattr(cli_runtime, "_CLI_TIMEOUT_S", 1)
    monkeypatch.setitem(cli_runtime._CLI_DEFS, "fake", {
        # 使用当前测试解释器，避免 Windows 没有 python3 命令时在启动阶段退出。
        "bins": [sys.executable],
        "delivery": "stdin",
        "build_args": lambda _: ["-c", "import time\nprint('x', flush=True)\ntime.sleep(30)"],
        "env": {},
    })
    chunks = []
    with pytest.raises(RuntimeError, match="超时"):
        for line in cli_runtime.run_cli_stream("fake", "s", "u"):
            chunks.append(line)
    assert chunks and chunks[0].strip() == "x"  # 挂起前的输出已正常流出
