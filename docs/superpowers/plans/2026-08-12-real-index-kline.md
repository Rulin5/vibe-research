# 真实指数 K 线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在“每日复盘”中用 TeaJoin 的真实历史 OHLC 展示 A 股及全球指数日 K，并在同源实时指数接口可用时每 30 秒更新当日未收盘 K 线。

**Architecture:** 新增独立的指数行情适配层，历史数据只调用 TeaJoin `index_daily`/`index_global`，盘中数据只接受 TeaJoin 实时接口返回的 open/high/low/price；服务层按标准证券标识合并最后一根日 K，并返回来源、时区、新鲜度和 partial 状态。前端通过已有 ECharts 6 渲染 K 线与成交量，不新增图表依赖。

**Tech Stack:** FastAPI、Python、TeaJoin Tushare-compatible API、React、TypeScript、ECharts 6、pytest、Vitest/Node tests

## Global Constraints

- A 股连续竞价时页面轮询间隔为 30 秒；服务端盘中缓存 TTL 为 25 秒，避免并发用户重复消耗供应商额度。
- 页面不展示“延迟”文案；只展示“盘中”“午间休市”“已收盘”“非交易日”和对应数据时间。
- A 股轮询仅在交易所交易日的 09:30:00–11:30:00、13:00:00–15:00:00（Asia/Shanghai）运行；11:30 后停止，13:00 恢复，15:00 后停止。
- 不从最新价反推历史 OHLC，不以前收盘价补开高低，不用零值填缺失行情。
- `index_daily`/`index_global` 的历史收盘日线是权威历史；实时快照只允许覆盖同一交易日的最后一根 `is_partial=true` K 线。
- TeaJoin 实时指数能力不可用时，返回最近完整交易日日线，页面只显示客观数据日期，不显示“实时”或“盘中”字样，也不静默切换其他供应商。
- A 股代码固定映射为 `000001.SH`、`399001.SZ`、`399006.SZ`、`000300.SH`；全球指数先使用已实测可用的 `SPX`、`DJI`、`IXIC`、`HSI`、`HKTECH`。
- API Key 继续只从 `backend/.env` 或环境变量读取，不进入响应、日志、前端或测试夹具。

---

### Task 1: TeaJoin 指数历史数据适配器

**Files:**
- Create: `backend/index_market.py`
- Create: `backend/tests/test_index_market.py`

**Interfaces:**
- Consumes: `teajoin.call(api_name, params, fields)`。
- Produces: `get_index_series(symbol: str, period: str = "1d", limit: int = 60) -> dict`。

- [ ] **Step 1: Write failing tests** covering A 股 `index_daily` and global `index_global`, ascending date normalization, numeric validation, duplicated trade-date rejection, and missing OHLC rejection.

```python
def test_history_is_normalized_oldest_first(monkeypatch):
    monkeypatch.setattr(index_market.teajoin, "call", lambda *args, **kwargs: [
        {"ts_code": "000001.SH", "trade_date": "20260811", "open": 3650, "high": 3690, "low": 3640, "close": 3680, "vol": 100, "amount": 200},
        {"ts_code": "000001.SH", "trade_date": "20260808", "open": 3600, "high": 3660, "low": 3590, "close": 3650, "vol": 90, "amount": 180},
    ])
    series = index_market.get_index_series("CN.SH.000001", limit=60)
    assert [row["trade_date"] for row in series["candles"]] == ["2026-08-08", "2026-08-11"]
    assert series["source_api"] == "index_daily"
```

- [ ] **Step 2: Run** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_index_market.py -q` and confirm failure because `index_market` does not exist.

- [ ] **Step 3: Implement** a fixed instrument registry containing vendor code, name, market, exchange, currency, timezone, source API and session calendar. Request only `ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount`; normalize dates and numbers; enforce `low <= min(open, close) <= max(open, close) <= high` where fields are present.

- [ ] **Step 4: Return typed status metadata**:

```python
{
    "symbol": "CN.SH.000001",
    "vendor_symbol": "000001.SH",
    "name": "上证指数",
    "market": "CN",
    "exchange": "SSE",
    "currency": "CNY",
    "timezone": "Asia/Shanghai",
    "frequency": "1d",
    "adjustment": "none",
    "source": "TeaJoin",
    "source_api": "index_daily",
    "retrieved_at": "ISO-8601",
    "as_of": "2026-08-11",
    "data_status": "fresh",
    "candles": [],
}
```

- [ ] **Step 5: Run** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_index_market.py -q` and confirm all adapter tests pass.

### Task 2: 同源实时合并、缓存与 API 契约

**Files:**
- Modify: `backend/index_market.py`
- Modify: `backend/app.py`
- Modify: `backend/tests/test_index_market.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: normalized historical series and optional TeaJoin realtime index snapshot.
- Produces: `GET /api/market/index-candles?symbols=CN.SH.000001,GLOBAL.SPX&period=1d&limit=60`.

- [ ] **Step 1: Write failing tests** for the batched endpoint, maximum 10 symbols, limit range 20–250, unknown symbol 422, upstream failure 502/503, 30-second cache reuse, and partial-candle merge.

```python
def test_same_day_realtime_snapshot_replaces_partial_candle():
    merged = index_market.merge_realtime(history, {
        "trade_date": "2026-08-12", "open": 3680, "high": 3700,
        "low": 3672, "price": 3694, "vol": 120, "amount": 260,
    })
    assert merged[-1]["close"] == 3694
    assert merged[-1]["is_partial"] is True
```

- [ ] **Step 2: Implement capability probing** for the documented TeaJoin realtime index API. Treat an empty response as unavailable, not as a zero quote; never retry permission errors. Record only stable error codes, symbol, source API, latency and request ID.

- [ ] **Step 3: Implement merge rules**: append a realtime row only when its local-market trade date is newer than history; replace only a history row with the same trade date; reject high/low/open/price inconsistencies; mark the current row `is_partial=true` until the exchange session is closed.

- [ ] **Step 4: Implement two caches**: completed history cache keyed by symbol/period/limit/data version with 15-minute TTL during market hours and longer post-close TTL; realtime snapshot cache keyed by symbol with 30-second TTL. Use a per-key lock to collapse concurrent refreshes.

- [ ] **Step 5: Implement strict degradation**. If realtime access is unavailable, preserve the completed history and return `data_status="historical"`, `realtime_available=false`, and a non-secret `status_reason="realtime_source_unavailable"`; the UI shows only the latest objective trading date.

- [ ] **Step 6: Run** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_index_market.py backend/tests/test_api.py -q` and confirm all affected backend tests pass.

### Task 3: ECharts K 线组件与每日复盘接入

**Files:**
- Create: `frontend/src/components/MarketKlineChart.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/DailyReview.tsx`
- Create: `frontend/tests/daily-review-kline.test.mjs`

**Interfaces:**
- Consumes: batched index-candles response.
- Produces: accessible responsive candlestick/volume chart with instrument tabs and explicit freshness state.

- [ ] **Step 1: Add TypeScript contracts** matching the backend exactly: `IndexCandle`, `IndexSeries`, and `IndexSeriesStatus`. Do not make OHLC optional when a candle is published.

- [ ] **Step 2: Write failing frontend source-contract tests** asserting Daily Review calls only the batch endpoint, uses no fixture candle data, renders market-session/source-failed states, and disposes ECharts instances.

- [ ] **Step 3: Implement `MarketKlineChart`** using the installed `echarts` package directly. Configure `candlestick`, aligned `bar` volume, MA20, `dataZoom`, crosshair tooltip, red-up/green-down colors, `ResizeObserver`, theme-aware colors, and `echarts.dispose()` cleanup.

- [ ] **Step 4: Replace snapshot-only index cards** with two wide tabbed chart cards: A 股 indices and global indices. Keep the selected quote summary above the chart and show `as_of`, local timezone, source, `is_partial`, and the objective market-session state.

- [ ] **Step 5: Add 30-second polling** only during A-share continuous trading sessions and while the tab is visible; pause during lunch break, after 15:00, on non-trading days and on `document.hidden`; refetch immediately at 13:00 or after returning visible, abort obsolete requests on tab changes, and keep the last valid response visible during a transient refresh failure with its objective data timestamp.

- [ ] **Step 6: Run** `npm --prefix frontend run test` and `npm --prefix frontend run build`; confirm tests and TypeScript production build pass.

### Task 4: 真实数据与金融口径验收

**Files:**
- Modify: `backend/tests/test_live.py`
- Modify: `backend/README.md`

**Interfaces:**
- Consumes: configured local TeaJoin credential and the running API.
- Produces: repeatable live-data verification procedure without exposing credentials.

- [ ] **Step 1: Add opt-in live tests** for one A-share index and one global index. Assert at least 20 ordered candles, valid OHLC relationships, no duplicate trade dates, plausible freshness, and returned vendor symbols.

- [ ] **Step 2: Document** that `index_daily` and `index_global` supply completed daily candles; realtime display requires the account's TeaJoin realtime-index capability. Document internal `fresh`, `historical`, `stale`, `source_failed`, and `invalid_data` meanings while keeping user-facing copy limited to the market-session status and objective data time.

- [ ] **Step 3: Run fast verification**:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_index_market.py backend/tests/test_api.py -q
npm --prefix frontend run test
npm --prefix frontend run build
```

- [ ] **Step 4: Run opt-in live verification** with the configured local key and record only source name, row count, latest trading date and validation outcome; never print request payloads containing the token.

- [ ] **Step 5: Manually verify** `/daily-review` at desktop and mobile widths, tab switching, tooltip OHLC, volume alignment, red/green convention, page-hide polling pause, market-session label, and no-data/source-failure messages.

## Release and rollback

- The new endpoint is additive; existing `/api/indices` and `/api/global/indices` remain compatible during rollout.
- Frontend can be rolled back independently to snapshot cards because no database migration is required.
- If TeaJoin realtime capability remains unavailable, ship only completed historical K lines with the exact latest trading date; do not enable intraday-refresh wording.
- Cost is bounded by shared caches: history at most once per symbol per 15 minutes and realtime at most once per symbol per 30 seconds regardless of concurrent users.
