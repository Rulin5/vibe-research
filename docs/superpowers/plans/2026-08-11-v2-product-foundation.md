# V2 产品基础能力 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有本地单用户投研工具升级为使用 PostgreSQL、用户名密码登录和真实数据口径的多用户产品基础层。

**Architecture:** 保持现有 FastAPI + React 的模块化单体架构。用户私有数据存 PostgreSQL 并由服务端 Session 推导用户身份；行情、资讯和板块仍由外部数据适配器提供，板块以可追溯快照发布，绝不以缓存旧值、零值或其他板块替代缺失数据。

**Tech Stack:** FastAPI、Pydantic、PostgreSQL 17、SQLAlchemy 2、Alembic、psycopg、React 19、React Router 7、现有 TeaJoin/Tushare 适配器。

## Global Constraints

- 登录方式固定为用户名 + 密码；手机号不作为登录凭证。
- 私有接口只能从 HttpOnly Session Cookie 得到 `user_id`，不得接收或信任客户端 `user_id`。
- 密码使用 Argon2id 哈希；Session 数据库只存随机 Token 的 SHA-256 哈希。
- 允许用户填写自己的 AI Key，但 Key 只可加密保存在服务端，永不写日志、永不返回前端、永不存入 localStorage。
- 模型与供应商基地址由服务端白名单控制；用户不能提交任意 Base URL。
- 所有板块必须来源可追溯。上游没有返回某字段时，返回明确的 `unavailable` 状态和原因，不得伪造完整数据。
- 不引入微服务、Redis、Kafka、Kubernetes、自动交易或真实资产配置建议。
- 数据库结构只通过 Alembic 迁移修改；部署先 expand，再迁移旧数据，最后才停止旧存储写入。
- Cookie 鉴权启用后，生产 CORS 必须为显式前端 Origin，且状态变更请求必须通过 Origin 与 CSRF 校验。

## Prerequisite: 指定 PostgreSQL 目标库

本机已有运行中的 PostgreSQL 17 服务（端口 5432），但仓库没有数据库连接配置。实施迁移前必须在不提交版本库的 `backend/.env` 写入：

```dotenv
VR_DATABASE_URL=postgresql+psycopg://<数据库用户>:<密码>@127.0.0.1:5432/<专用数据库名>
VR_SESSION_SECRET=<至少32字节随机值>
VR_CREDENTIAL_ENCRYPTION_KEY=<32字节base64密钥>
VR_ALLOW_ORIGINS=http://127.0.0.1:5899
```

建议专用数据库名为 `vibe_research`，不得使用 `postgres` 系统库，也不得把连接串、Session Secret、AI Key 或 TeaJoin Key 写进代码、测试断言或文档示例中的真实值。

---

### Task 1: 数据库、迁移与用户数据模型 — completed 2026-08-11

**Files:**
- Create: `backend/db.py`
- Create: `backend/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/20260811_01_user_foundation.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_user_models.py`

**Interfaces:**
- Produces `get_session() -> Generator[Session, None, None]`。
- Produces `User`, `SessionRecord`, `WatchlistItem`, `PortfolioHolding`, `ClosedPosition`, `UserReport`, `ResearchNote`, `UserAiCredential`, `AiUsageEvent` ORM 模型。
- Produces `normalize_security(code: str) -> tuple[str, str]`，返回 `(market, code)`；当前只接受六位 A 股代码。

- [x] **Step 1: 写失败测试，规定用户数据的唯一约束和隔离字段。**

```python
def test_watchlist_is_unique_per_user(session, user_factory):
    first = user_factory(username="alpha")
    second = user_factory(username="beta")
    session.add_all([
        WatchlistItem(user_id=first.id, market="CN", code="600519"),
        WatchlistItem(user_id=second.id, market="CN", code="600519"),
    ])
    session.commit()
    assert session.query(WatchlistItem).filter_by(code="600519").count() == 2
```

- [x] **Step 2: 运行失败测试。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests\test_user_models.py -q`

Expected: 因 `models` 模块与模型尚不存在而失败。

- [x] **Step 3: 添加数据库运行时与 Alembic 初始迁移。**

迁移必须创建以下关键约束和索引：

```sql
CREATE UNIQUE INDEX uq_users_username_ci ON users (lower(username));
CREATE UNIQUE INDEX uq_sessions_token_hash ON sessions (token_hash);
CREATE UNIQUE INDEX uq_watchlist_user_security ON watchlist_items (user_id, market, code);
CREATE INDEX ix_holdings_user_id ON portfolio_holdings (user_id);
CREATE INDEX ix_reports_user_id ON user_reports (user_id);
CREATE INDEX ix_notes_user_updated_at ON research_notes (user_id, updated_at DESC);
CREATE INDEX ix_ai_usage_user_created_at ON ai_usage_events (user_id, created_at DESC);
```

`portfolio_holdings` 使用 `numeric` 保存数量与成本，`closed_positions` 保存成交日期、成交价、数量与成本；不得用浮点数作为数据库货币口径。所有用户私有表均有不可空 `user_id` 外键和 `created_at`/`updated_at`。

- [x] **Step 4: 运行模型测试和迁移静态检查。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests\test_user_models.py -q`

Expected: PASS。

Run: `backend\.venv\Scripts\alembic.exe -c alembic.ini upgrade head`

Expected: 仅在 `VR_DATABASE_URL` 指向专用开发数据库后成功执行一次可重复迁移。

### Task 2: Session 鉴权、授权依赖与安全边界

**Files:**
- Create: `backend/auth.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_auth_api.py`

**Interfaces:**
- `POST /api/auth/register {username, password}` 返回公开用户资料并设置 `vr_session` Cookie。
- `POST /api/auth/login {username, password}` 轮换 Session 并设置 Cookie。
- `POST /api/auth/logout` 使当前 Session 失效并清除 Cookie。
- `GET /api/auth/me` 返回 `{id, username, created_at}`；未登录为 `401 auth_required`。
- `require_current_user(request, db) -> User` 是所有私有路由唯一的身份入口。

- [ ] **Step 1: 写失败测试，规定 Cookie 身份而非请求参数身份。**

```python
def test_user_cannot_read_another_users_watchlist(client, user_a, user_b):
    token_a = login(client, user_a.username, "correct-password")
    create_watchlist_item(client, token_a, "600519")
    token_b = login(client, user_b.username, "correct-password")
    response = client.get("/api/watchlist", cookies={"vr_session": token_b})
    assert response.status_code == 200
    assert response.json()["data"] == []

def test_private_api_rejects_client_supplied_user_id(client):
    response = client.get("/api/watchlist?user_id=1")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "auth_required"
```

- [ ] **Step 2: 运行失败测试。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -q`

Expected: 因认证接口和依赖不存在而失败。

- [ ] **Step 3: 实现最小认证闭环。**

用户名规则为 `3..32` 个小写英文字母、数字或下划线；密码规则为 `12..128` 字符。注册时比较不区分大小写的用户名唯一性。每次登录均创建新 Session、使同一浏览器旧 Session 失效；Session 有过期时间，数据库只保存 `sha256(raw_token)`。

所有 `POST`、`DELETE` 私有路由验证：允许的 Origin、`X-CSRF-Token` 与非 HttpOnly `vr_csrf` Cookie 相等、Session 有效。生产环境 `allow_origins` 不得是 `*`，Cookie 设置 `httponly=True`、`secure=True`、`samesite="lax"`。

- [ ] **Step 4: 运行认证、越权和现有 API 回归测试。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py tests\test_api.py -q`

Expected: PASS；用未登录 Cookie 访问私有资源为 401，用另一个用户 Cookie 读取资源为空或 404，绝不返回其他用户对象。

### Task 3: 自选、持仓、研报和研究记录的按用户持久化

**Files:**
- Create: `backend/user_data.py`
- Modify: `backend/app.py`
- Modify: `backend/portfolio.py`
- Modify: `backend/myreports.py`
- Create: `backend/tests/test_user_assets_api.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/watchlist.ts`
- Modify: `frontend/src/lib/notes.ts`
- Modify: `frontend/src/pages/Watchlist.tsx`
- Modify: `frontend/src/pages/Portfolio.tsx`
- Modify: `frontend/src/pages/MyReports.tsx`
- Modify: `frontend/src/pages/Notes.tsx`

**Interfaces:**
- `GET|POST|DELETE /api/watchlist` 使用当前用户。
- `GET /api/portfolio`、`POST|DELETE /api/portfolio/holdings/{holding_id}`、`POST|DELETE /api/portfolio/closed-positions/{position_id}` 使用当前用户。
- `GET|POST /api/research-notes`、`PATCH|DELETE /api/research-notes/{note_id}` 使用当前用户。
- `GET|POST /api/user-reports`、`GET|DELETE /api/user-reports/{report_id}` 使用当前用户。

- [ ] **Step 1: 写失败测试，规定对象级授权。**

```python
def test_report_download_requires_owning_user(client, report_factory, user_a, user_b):
    report = report_factory(owner=user_a, name="private.pdf")
    token_b = login(client, user_b.username, "correct-password")
    response = client.get(f"/api/user-reports/{report.id}", cookies={"vr_session": token_b})
    assert response.status_code == 404

def test_create_note_binds_session_user_not_payload_user_id(client, user_a):
    token = login(client, user_a.username, "correct-password")
    response = client.post(
        "/api/research-notes",
        json={"title": "复盘", "content": "正文", "user_id": "other-user"},
        cookies={"vr_session": token},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: 运行失败测试。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests\test_user_assets_api.py -q`

Expected: 因路由和数据服务不存在而失败。

- [ ] **Step 3: 实现用户资产服务和兼容迁移。**

新写入全部进入 PostgreSQL。保留现有 `portfolio.py` 和 `myreports.py` 只读导入适配器，新增“导入本机旧数据”确认接口；导入前展示数量，导入使用幂等键 `(user_id, source, source_record_id)`，成功后不删除旧本地文件。

研报文件落到 `VR_REPORTS_DIR/<user_uuid>/<report_uuid>.<ext>`；数据库保存原文件名、MIME、大小、摘要、存储键。下载和删除均以 `report_id + current_user.id` 查询，找不到一律返回 404。上传继续限制扩展名、MIME、大小和 base64 解码错误。

- [ ] **Step 4: 将前端本地读写替换为带 Cookie 的 API 客户端。**

所有 `fetch` 使用 `credentials: "include"`。移除 `vr-watchlist` 和 `vr-notes` 作为主存储；仅保留一次性读取并请求导入的兼容代码。持仓删除从代码参数改为持仓 UUID，避免同代码多笔持仓发生误删。

- [ ] **Step 5: 运行 API 和前端契约测试。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests\test_user_assets_api.py tests\test_auth_api.py -q`

Expected: PASS。

Run: `node --test tests\sector-data-contract.test.mjs`

Expected: PASS，随后为用户资产新增独立的前端契约测试。

### Task 4: 前端登录态、路由保护、统一股票搜索与导航

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/components/auth/AuthProvider.tsx`
- Create: `frontend/src/components/auth/RequireAuth.tsx`
- Create: `frontend/src/pages/Login.tsx`
- Create: `frontend/src/pages/Register.tsx`
- Create: `frontend/src/components/stocks/StockSearch.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx`
- Modify: `frontend/src/pages/MyFocus.tsx`
- Test: `frontend/tests/auth-route-contract.test.mjs`
- Test: `frontend/tests/stock-search-contract.test.mjs`

**Interfaces:**
- `useAuth()` 返回 `{user, loading, login, logout, refresh}`。
- `StockSearch({onSelect})` 查询 `/api/stocks/search?query=`，返回股票名称、代码、市场和数据源。
- `/watch/*`、用户研报和研究记录页面由 `RequireAuth` 保护；未登录跳转 `/login?next=<path>`。

- [ ] **Step 1: 写失败的路由与搜索契约测试。**

```javascript
test("private watch route is wrapped by RequireAuth", () => {
  const source = readFileSync("src/router.tsx", "utf8");
  assert.match(source, /path: "\/watch"[\s\S]*RequireAuth/);
});

test("stock search accepts name and code query without frontend filtering", () => {
  const source = readFileSync("src/components/stocks/StockSearch.tsx", "utf8");
  assert.match(source, /api\.stockSearch\(query\)/);
  assert.doesNotMatch(source, /replace\(\/\[^\\d\]/);
});
```

- [ ] **Step 2: 运行失败测试。**

Run: `node --test tests\auth-route-contract.test.mjs tests\stock-search-contract.test.mjs`

Expected: FAIL，因为认证组件和统一搜索组件尚不存在。

- [ ] **Step 3: 实现登录态和统一搜索。**

应用启动调用 `/api/auth/me`，不以 localStorage 判断登录。侧栏显示用户名和退出按钮；一级导航文案改为“我的投资”，二级导航固定为“自选股、我的持仓、我的研报、研究记录”。搜索框防抖 250ms，支持代码、代码前缀、股票名和名称片段；选择结果跳转 `/stock-data?code=<六位代码>`，并为自选/持仓录入复用同一结果。

- [ ] **Step 4: 运行前端测试与构建。**

Run: `node --test tests\auth-route-contract.test.mjs tests\stock-search-contract.test.mjs tests\sector-data-contract.test.mjs`

Expected: PASS。

Run: `npm run build`

Expected: Vite build exit code 0。

### Task 5: 真实板块全量目录、快照状态与用户自填 AI Key

**Files:**
- Modify: `backend/astock.py`
- Modify: `backend/sector_refresh.py`
- Modify: `backend/sector_snapshot.py`
- Modify: `backend/app.py`
- Modify: `frontend/src/pages/Sectors.tsx`
- Modify: `frontend/src/pages/SectorDetail.tsx`
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/lib/llm.ts`
- Create: `backend/ai_credentials.py`
- Create: `backend/tests/test_sector_coverage.py`
- Create: `backend/tests/test_ai_credentials.py`

**Interfaces:**
- 板块行包含 `kind, code, name, as_of, data_status, unavailable_reason, source, source_api, retrieved_at`；当且仅当 `data_status == "complete"` 时才有完整当日行情和经校验成员股。
- `GET /api/all-sectors` 返回全量可识别目录与每行状态；`GET /api/sector-members` 仅对完整、同一快照的板块返回成员股。
- `PUT|DELETE /api/ai-credentials/{provider}` 只允许当前用户操作自己的加密凭据；`GET /api/ai/models` 返回服务端白名单。

- [ ] **Step 1: 写失败测试，禁止静默丢弃或伪造板块。**

```python
def test_catalog_row_without_today_quote_is_explicitly_unavailable(snapshot, catalog_only_code):
    row = find_sector(snapshot, code=catalog_only_code)
    assert row["data_status"] == "unavailable"
    assert row["unavailable_reason"] == "daily_quote_not_returned"
    assert row["pct_change"] is None

def test_incomplete_sector_never_returns_members(client, complete_snapshot_with_one_unavailable_row, catalog_only_code):
    response = client.get(f"/api/sector-members?kind=概念&code={catalog_only_code}")
    assert response.status_code == 409
```

- [ ] **Step 2: 运行失败测试。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests\test_sector_coverage.py tests\test_ai_credentials.py -q`

Expected: FAIL，因为当前快照会过滤上游未满足成员校验的板块，且没有用户加密凭据服务。

- [ ] **Step 3: 实现真实数据状态与完整覆盖诊断。**

以供应商目录为每个交易日的可识别集合，逐行记录目录来源、日行情来源、成员股来源、采集时间和校验结果。完整数据发布时保留同一快照 ID；无日行情、无成员股、日期不一致、成员数量不一致、上游失败分别写入不可用原因。页面将“可用当日数据”和“当前不可用”分区展示，不把不可用项伪装成涨跌为 0 的可用板块。

刷新任务必须有限重试、退避、总时限和进度持久化；失败快照不得覆盖上一次已验证的完整快照。对供应商不提供的全量日行情，保留事实性不可用状态；若业务要求每个目录项都有每日行情，必须新增已授权且覆盖该目录的行情供应商后才能承诺该结果。

- [ ] **Step 4: 实现用户自填 AI Key 的加密与额度边界。**

用户填写 Key 后，服务端使用 `VR_CREDENTIAL_ENCRYPTION_KEY` 做 AES-GCM 加密保存；列表 API 只返回 `provider`、掩码后缀、模型可用性和更新时间。`/api/chat`、`/api/debate`、`/api/reflect` 不再接受 `baseURL` 或明文 `apiKey`，只接受受白名单约束的 `model_id`；每次执行记录用户、模型、输入输出 token、成本、结果状态和错误码。

- [ ] **Step 5: 运行数据、鉴权和前端回归。**

Run: `backend\.venv\Scripts\python.exe -m pytest tests -m "not live" -q`

Expected: PASS。

Run: `node --test tests\sector-data-contract.test.mjs tests\auth-route-contract.test.mjs tests\stock-search-contract.test.mjs`

Expected: PASS。

Run: `npm run build`

Expected: exit code 0。

## 人工验收路径

1. 注册用户 A 和 B，分别登录并添加同一股票；确认自选、持仓、研报和笔记互不可见。
2. 用 B 的浏览器地址直接请求 A 的研报 UUID；确认返回 404，且下载目录中不会泄露文件名或内容。
3. 使用股票名称片段、完整代码和代码前缀检索，确认均能进入正确的个股页。
4. 触发板块刷新，确认每张卡都显示供应商、交易日、采集时间和数据状态；上游缺失显示原因，不显示伪造数字。
5. 以用户 A 填写 AI Key，确认前端刷新后只显示掩码；用用户 B 登录后不能看到或调用 A 的 Key。

## 计划边界与后续包

本计划先完成 P0 的身份、私有数据和安全边界，并将板块真实性与 AI Key 的基础契约接入。每日复盘图表化、资讯雷达的页面整理、静态资产配置预览属于下一份 P1 页面计划；它们必须在本计划的登录态、用户数据和真实板块状态稳定后开始。
