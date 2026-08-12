# 多用户认证、数据隔离与 AI 安全接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. Every implementation change starts with a failing test.

**Goal:** 将当前单机、全局文件存储的个人数据功能迁移为经过认证的 PostgreSQL 用户资源，并将 AI 密钥从浏览器明文配置迁移为服务端按用户加密保管。

**Architecture:** 使用数据库保存的随机不透明 Session，而不是可自解释 JWT。浏览器只持有 HttpOnly Session Cookie 与独立的 CSRF Cookie；每个私有查询均在服务层按 `current_user.id` 过滤，所有跨用户资源访问统一返回 404。公共行情、资讯和板块数据保持无登录读取，避免把公共金融数据混入用户授权逻辑。AI 请求仅可引用当前用户已加密保存的凭据和服务端模型白名单，前端不再传输 API Key 或 Base URL。

**Tech Stack:** FastAPI、SQLAlchemy 2、Alembic、PostgreSQL 17、`argon2-cffi`（Argon2id）、`cryptography`（AES-GCM）、React 18、React Router、Vite、Node test、pytest。

## 现状分析与准入结论

- 已具备 PostgreSQL、Alembic，以及 `users`、`sessions`、`watchlist_items`、持仓、研报、笔记和 AI 凭据表；字段均有不可为空的 `user_id`，可作为隔离基础。
- 当前 `/api/portfolio`、`/api/myreports` 仍读取进程/文件级全局数据；前端自选和笔记仍在 `localStorage`，所以任何登录页面本身都不能产生隔离。
- 当前 `/api/chat`、`/api/debate`、`/api/reflect` 接受前端传来的 `apiKey` 与 `baseURL`；这会使密钥出现在浏览器存储、请求体和潜在日志中，不能作为正式多用户方案。
- 旧 `portfolio.py` 和 `myreports.py` 没有数据所有者。不得自动导入或继续公开这些数据，否则首个注册用户可以错误取得历史全局数据。旧文件只保留作离线人工备份；后续如需迁移，必须由本机管理员提供“旧文件记录 → 指定 user_id”的一次性离线映射工具。
- 准入结论：方案可实施，但仅在以下四个工作包全部通过后才能称为“多用户可用”。在完成前，保持本地开发部署，禁止以正式多用户版本发布。

## 全局安全与兼容约束

- 密码使用 Argon2id；密码、Session 原文、CSRF 值、AI Key、数据库 URL 绝不记录日志或写入响应。
- Session 原文由 `secrets.token_urlsafe(32)` 生成，数据库只保存 SHA-256 摘要；有效期为 7 天，登录时新建会话，退出时撤销。
- Cookie 名为 `vr_session`（HttpOnly、SameSite=Lax、Path=/）和 `vr_csrf`（非 HttpOnly、SameSite=Lax、Path=/）。`VR_COOKIE_SECURE` 在生产必须为 `true`；本地 HTTP 通过显式 `false` 运行。
- 所有 `POST`、`PUT`、`PATCH`、`DELETE` 私有 API 均要求 `X-CSRF-Token` 等于 `vr_csrf` Cookie；登录、注册也要求同源 Origin，首次注册/登录的 CSRF Cookie 由服务端在响应中设置。
- CORS 必须启用 `allow_credentials=True`，且 `VR_ALLOW_ORIGINS` 不得为 `*`。本机只允许 `http://127.0.0.1:5900`。
- 公开行情接口不附加身份；私有资源未认证返回 401，非本人 ID、报告 ID 或持仓 ID 均返回 404，不泄露资源存在性。
- 新的私有接口沿用当前前端路径：`/api/portfolio`、`/api/myreports`；删除持仓和清仓记录改为 UUID 路径。旧全局文件不再由 HTTP API 读取。

## 文件与职责

- Create: `backend/auth.py` — 密码散列、Session、当前用户依赖、CSRF/Origin 校验。
- Create: `backend/user_assets.py` — 自选、持仓、已清仓、笔记的用户范围数据库服务。
- Create: `backend/report_storage.py` — 研报文件验证、原子落盘、用户范围元数据与下载路径。
- Create: `backend/ai_credentials.py` — AES-GCM 凭据加解密、模型白名单、按用户取用凭据。
- Modify: `backend/app.py` — 认证和私有资源路由；移除请求体 AI Key/Base URL 契约。
- Modify: `backend/requirements.txt`、`backend/.env.example` — 固定安全依赖及只含占位符的安全配置。
- Modify: `backend/alembic/versions/20260811_01_user_foundation.py` — 不修改已执行迁移；若实现确需新增列，只能创建新的 expand migration。
- Create: `backend/tests/test_auth_api.py`、`backend/tests/test_user_assets_api.py`、`backend/tests/test_ai_credentials.py`。
- Create: `frontend/src/lib/auth.ts`、`frontend/src/components/auth/AuthProvider.tsx`、`frontend/src/components/auth/RequireAuth.tsx`、`frontend/src/pages/Login.tsx`、`frontend/src/pages/Register.tsx`。
- Modify: `frontend/src/main.tsx`、`frontend/src/router.tsx`、`frontend/src/lib/api.ts`、`frontend/src/lib/llm.ts`、`frontend/src/lib/agents.ts`、`frontend/src/lib/ndjson.ts`、`frontend/src/pages/{Watchlist,Portfolio,MyReports,Notes,Settings}.tsx`、`frontend/src/components/{layout/Layout,ui/SaveNoteButton}.tsx`。
- Create: `frontend/tests/auth-route-contract.test.mjs`、`frontend/tests/private-api-contract.test.mjs`。

---

### 工作包 1：认证、Session、CSRF 与 CORS

**接口契约：**

```text
POST /api/auth/register { username, password } -> 201 { data: { id, username } }
POST /api/auth/login    { username, password } -> 200 { data: { id, username } }
POST /api/auth/logout   -> 204
GET  /api/auth/me       -> 200 { data: { id, username } } | 401
```

- [ ] **Step 1: 写失败测试。** `test_auth_api.py` 使用临时 PostgreSQL schema/事务，断言注册时密码不是明文、Cookie 带 HttpOnly/SameSite、错误密码为 401、退出后 `/me` 为 401、缺失/错误 CSRF 的私有写入为 403、`VR_ALLOW_ORIGINS=*` 启动失败。
- [ ] **Step 2: 运行失败测试。**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_auth_api.py -q
```

预期：失败，原因是 `auth.py` 和 `/api/auth/*` 不存在。

- [ ] **Step 3: 实现最小认证服务。** `auth.py` 提供 `hash_password(password) -> str`、`verify_password(password, encoded) -> bool`、`create_session(db, user_id) -> str`、`require_current_user(request, db) -> User`、`require_csrf(request) -> None`。用户名仅允许 3–32 位 ASCII 字母、数字和下划线；密码要求 12–128 字符。使用 Argon2id 默认安全参数，比较使用库的常量时间验证；Session 查询同时校验未撤销和未过期。
- [ ] **Step 4: 接入路由与 CORS。** 在 `app.py` 给写接口添加 `Depends(require_csrf)`，给私有接口添加 `Depends(require_current_user)`；将 CORS 方法扩展到 PUT/PATCH，明确拒绝通配 Origin + credential 组合。Cookie 设置只通过集中 helper，不在路由重复。
- [ ] **Step 5: 验证通过并做数据库状态检查。**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_auth_api.py backend\tests\test_user_models.py -q
Push-Location backend; .\.venv\Scripts\alembic.exe current; Pop-Location
```

预期：认证测试通过，数据库仍处于 `20260811_01 (head)`；本工作包不修改数据库结构。

### 工作包 2：用户资产服务与跨用户隔离

**接口契约：**

```text
GET/POST/DELETE /api/watchlist
GET /api/portfolio
POST /api/portfolio/holding { code, shares, cost } -> holding UUID
DELETE /api/portfolio/holding/{holding_id}
POST /api/portfolio/close { code, date, price, shares, cost } -> closed-position UUID
DELETE /api/portfolio/close/{position_id}
GET/POST/DELETE /api/notes and /api/notes/{note_id}
GET/POST/DELETE /api/myreports and /api/myreports/{report_id}
GET /api/myreports/file/{report_id}
```

- [ ] **Step 1: 写失败测试。** 在 `test_user_assets_api.py` 建立 A、B 两个已登录客户端。A 添加自选、持仓、已清仓、笔记、PDF 研报；B 列表必须为空，直接删除/下载 A 的 UUID 必须是 404。另断言缺失登录为 401、重复自选幂等、报告非法类型为 400、报告数据库保存的路径以 `VR_REPORTS_DIR/<user_id>/` 开头。
- [ ] **Step 2: 运行失败测试。**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_user_assets_api.py -q
```

预期：失败，原因是当前接口仍读取 `portfolio.py`/`myreports.py` 全局数据且无当前用户依赖。

- [ ] **Step 3: 实现用户范围服务。** `user_assets.py` 的每个读取入口第一个过滤条件为 `model.user_id == current_user.id`。金额和数量在 API 边界转换为 `Decimal(str(value))`；不使用 float 做持仓成本计算。每笔持仓维持独立 UUID，不把同代码多笔记录合并；返回时才调用公共行情适配器补充报价，行情失败需标记 `quote_status`，不得填充 0。
- [ ] **Step 4: 实现安全研报落盘。** `report_storage.py` 复用原有扩展名/MIME/base64 检验，写入同用户目录的临时文件后原子替换，再提交 `UserReport` 元数据。任何 DB 写入失败均删除新文件；删除先提交“不可访问”状态，文件删除失败只留下无引用孤儿文件并记录不含文件内容的错误，绝不返回给其他用户。下载/删除统一按 `(report_id, user_id)` 查询。
- [ ] **Step 5: 替换 HTTP 路由。** 私有路由只调用新服务，不再导入 `portfolio.py` 或 `myreports.py`。旧文件原样保留且不经 HTTP 暴露；响应内不再出现“只存本地、不上传”的旧文案。保留当前数据格式的无破坏字段，并新增 `id` 给持仓和已清仓记录。
- [ ] **Step 6: 验证隔离与回归。**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_user_assets_api.py backend\tests\test_reports_and_security.py backend\tests\test_api.py -q
```

预期：跨用户访问全为 404，原有公共 API 测试通过。若旧测试依赖全局私有数据，应改为认证用户场景而不是恢复旧全局行为。

### 工作包 3：前端登录态、受保护路由与私有 API 客户端

- [ ] **Step 1: 写失败契约测试。** `auth-route-contract.test.mjs` 断言 `AuthProvider` 在启动时调用 `/api/auth/me`、`/watch/*` 与 `/settings` 被 `RequireAuth` 包裹、未登录跳转 `/login?next=`；`private-api-contract.test.mjs` 断言私有写入发送 `credentials: "include"` 和 `X-CSRF-Token`，并且自选/笔记不再作为主存储调用 `localStorage`。
- [ ] **Step 2: 运行失败测试。**

```powershell
Push-Location frontend; node --test tests\auth-route-contract.test.mjs tests\private-api-contract.test.mjs; Pop-Location
```

预期：失败，因为认证 Provider、路由守卫和 CSRF API 客户端尚不存在。

- [ ] **Step 3: 实现登录流。** 新增注册、登录页和 `AuthProvider`，只以 `/api/auth/me` 作为登录真相；不在 localStorage 保存用户、Session 或密码。`api.ts` 集中读取 `vr_csrf` Cookie 并为变更请求补充 header，遇到 401 清空内存态并跳登录。布局显示当前用户名和退出入口。
- [ ] **Step 4: 接通私有页面。** `Watchlist`、`Portfolio`、`MyReports`、`Notes` 和 `SaveNoteButton` 改用新 API，并处理加载、401、403、404、网络失败状态。保留主题和侧栏折叠等纯界面偏好在 localStorage；不自动上传旧 `vr-watchlist`、`vr-notes`，以免将无法判定所有权的数据写入账户。
- [ ] **Step 5: 验证浏览器路径与构建。**

```powershell
Push-Location frontend
node --test tests\auth-route-contract.test.mjs tests\private-api-contract.test.mjs tests\sector-data-contract.test.mjs tests\theme-sidebar-contract.test.mjs
npm run build
Pop-Location
```

预期：全部测试通过，Vite 构建退出码 0。

### 工作包 4：按用户加密 AI 凭据与受控模型调用

**接口契约：**

```text
GET    /api/ai/models -> { data: [{ provider, model_id, display_name }] }
GET    /api/ai-credentials -> { data: [{ provider, key_suffix, updated_at }] }
PUT    /api/ai-credentials/{provider} { api_key } -> 204
DELETE /api/ai-credentials/{provider} -> 204
POST   /api/chat    { messages, context, model_id }
POST   /api/debate  { code, rounds, model_id }
POST   /api/reflect { source, title, model_id }
```

- [ ] **Step 1: 写失败测试。** `test_ai_credentials.py` 断言保存后数据库密文不等于明文、列表只返回尾缀、B 不能读取/删除/调用 A 的凭据、未知 `provider/model_id` 为 422、AI 请求体中出现 `apiKey` 或 `baseURL` 为 422、未配置凭据为 409。测试对模型执行器使用受控替身，绝不调用付费模型。
- [ ] **Step 2: 运行失败测试。**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_credentials.py -q
```

预期：失败，因为当前 API 仍接受明文 LLMConfig。

- [ ] **Step 3: 实现加密凭据服务。** `ai_credentials.py` 从 `VR_CREDENTIAL_ENCRYPTION_KEY` 读取 URL-safe base64 的 32 字节密钥；使用 AES-GCM，每条密文使用独立 96-bit nonce，并以 `user_id:provider` 作 associated data。模型白名单是服务端常量，当前仅注册已配置的 StepFun provider/model；任何调用都以当前用户、白名单模型和解密后的内存密钥构造下游配置。
- [ ] **Step 4: 收紧模型 API。** 删除 `LLMConfig.baseURL` 与 `LLMConfig.apiKey` 请求字段，拒绝额外敏感字段；模型响应、日志和 `AiUsageEvent` 仅写 provider/model、token、微美元成本、状态、稳定错误码和 request_id，不写 prompt、回复或密钥。为流式生成设定请求超时、最大消息数、最大单消息字符数和取消传播。
- [ ] **Step 5: 接通设置页与流式客户端。** `Settings` 仅提交一次 API Key 并随后只显示掩码尾缀；`llm.ts`/`agents.ts` 只发送 `model_id`。所有流式 fetch 均带 Cookie 和 CSRF header。用户退出或切换账户后不保留任何 AI 凭据缓存。
- [ ] **Step 6: 完整验证。**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -m "not live" -q
Push-Location frontend
node --test tests\auth-route-contract.test.mjs tests\private-api-contract.test.mjs tests\sector-data-contract.test.mjs tests\theme-sidebar-contract.test.mjs
npm run build
Pop-Location
```

预期：无 live/付费 AI 调用，所有测试通过，构建成功。

## 人工验收与发布门槛

1. 在两个独立浏览器会话注册 A/B；分别写入相同股票，确认自选、持仓、笔记、研报都互不可见。
2. 复制 A 的持仓 UUID、笔记 UUID、研报 UUID 到 B 会话请求，全部得到 404；未登录时私有列表得到 401；省略 CSRF header 的写入得到 403。
3. 登录后刷新页面仍保持登录；退出后刷新 `/watch/*` 必须回到登录页，原 Cookie 已失效。
4. A 填入自己的 AI Key 后刷新设置页只看到掩码；B 既看不到也无法使用 A 的凭据。执行一次非付费测试替身后，数据库日志事件不含密钥、提示词或模型输出。
5. 生产部署前设 `VR_COOKIE_SECURE=true`、非通配 `VR_ALLOW_ORIGINS`、强随机 Session/凭据密钥，并执行 Alembic 状态检查和完整测试。未满足任一项不得发布。

## 风险与后续事项

- 旧全局文件数据不会自动出现在任何账户中。这是阻止历史数据所有权错配的必要限制；若用户需要迁移，应单独实现需管理员确认和审计的离线导入工具。
- 当前 AI 服务端密钥与用户密钥必须分离；测试期间不得向真实模型提交用户数据或发起付费调用。
- 认证登录限流、密码重置、邮件/手机验证、审计事件保留策略属于下一安全工作包。在公网开放前，至少需补充持久化登录限流和安全告警。
