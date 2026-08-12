# TeaJoin 板块数据与股票搜索 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让板块中心使用可追溯的 TeaJoin/Tushare 板块及成分数据，并支持按 A 股代码或证券名称搜索、从板块详情直接打开具体股票。

**Architecture:** 新建一个轻量 TeaJoin HTTP 适配器，从环境变量读取密钥并统一校验 Tushare 响应。板块列表继续使用现有公开行情展示即时涨跌，详情成分与股票搜索使用 TeaJoin 的 `ths_member`、`dc_member` 和 `stock_basic`；前端仅消费新的后端契约。

**Tech Stack:** FastAPI、Python requests、React 19、TypeScript、Vite、pytest、Node test runner。

## Global Constraints

- API Key 仅允许放入忽略的 `backend/.env` 或环境变量 `TEAJOIN_API_KEY`，不得硬编码、记录或返回给浏览器。
- TeaJoin 请求设置 15 秒超时、单实例最小 0.2 秒间隔，并把上游错误和空数据区分返回。
- 板块页面必须明确显示数据来源和时间口径；不把历史/收盘数据标成实时。

---

### Task 1: TeaJoin 适配器和安全配置

**Files:**
- Create: `backend/teajoin.py`
- Create: `backend/.env`
- Modify: `backend/.env.example`
- Modify: `backend/tests/test_teajoin.py`

- [ ] **Step 1: Write failing tests** for an absent key, Tushare `fields/items` normalization, and an upstream error.
- [ ] **Step 2: Run** `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_teajoin.py -q` and confirm expected failure.
- [ ] **Step 3: Implement** `call(api_name, params, fields)` with a private key loader, timeout, rate limit, and typed provider exceptions.
- [ ] **Step 4: Run** the focused tests and a real `stock_basic` smoke call without printing credentials.

### Task 2: Real sector membership and stock search API

**Files:**
- Modify: `backend/astock.py`
- Modify: `backend/app.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing API-contract tests** for `GET /api/sector-members` and `GET /api/stocks/search`, including code/name matching and provider-error mapping.
- [ ] **Step 2: Run** `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_api.py -q` and confirm expected failure.
- [ ] **Step 3: Implement** normalized `SectorMember` and `StockSearchResult` responses, a 10-minute list cache, 5-minute membership/search cache, and no silent empty fallback for upstream failure.
- [ ] **Step 4: Run** focused backend tests plus a live smoke request for one sector and `贵州茅台`.

### Task 3: Board detail constituents and search UX

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/Sectors.tsx`
- Modify: `frontend/src/pages/SectorDetail.tsx`
- Create: `frontend/tests/sector-data-contract.test.mjs`

- [ ] **Step 1: Write failing static contract tests** for both new API methods and routes to `/stock-data?code=...`.
- [ ] **Step 2: Run** `cd frontend; node --test tests/sector-data-contract.test.mjs` and confirm expected failure.
- [ ] **Step 3: Implement** debounced code/name search, source/error states, and a member list with clickable stocks.
- [ ] **Step 4: Run** frontend tests and `npm run build`.

### Task 4: End-to-end local verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document** `TEAJOIN_API_KEY` setup without exposing its value.
- [ ] **Step 2: Run** non-live backend suite, frontend tests, build, then start the API and make representative HTTP requests.
- [ ] **Step 3: Verify** no tracked source contains the supplied credential.
