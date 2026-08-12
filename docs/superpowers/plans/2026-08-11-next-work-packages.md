# 多用户闭环与 AI 安全接入：下一轮工作包计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. Each production change starts with a failing test.

**Goal:** 把已完成的后端身份与数据归属能力接到真实前端使用路径，消除浏览器中的 AI 明文密钥，并完成多账户端到端验收。

**Architecture:** 公共金融数据继续匿名读取；自选、持仓、已清仓、研报、笔记和 AI 凭据全部通过 Cookie Session 绑定当前用户。前端不以 localStorage 作为任何私有业务数据的主存储；仅允许主题、侧栏状态和未提交表单草稿留在本机。所有 AI 调用只传服务端白名单 `model_id`，服务端从当前用户的 AES-GCM 密文凭据构造调用配置。

**Global constraints:** 不自动导入旧全局文件数据；跨用户资源一律 404；行情失败使用 `null + status`，不得以零代替；不向真实付费模型运行自动化测试；公网发布前必须有持久化登录限流。

---

### 工作包 1：前端自选股与跨页面关注列表切换到私有 API

**范围：** `frontend/src/lib/api.ts`、`frontend/src/pages/Watchlist.tsx`、`DailyReview.tsx`、`Intel.tsx`、`frontend/src/lib/watchlist.ts`、`frontend/tests/private-assets-contract.test.mjs`。

**实施：**

1. 先写契约测试：`Watchlist` 不再引用 `loadWatch/saveWatch`；页面通过 `api.watchlist()` 读取，通过 `api.addWatchlist(code)` 和 `api.deleteWatchlist(id)` 写入；`DailyReview`、`Intel` 通过同一只读查询取得代码清单。
2. 在 `api.ts` 增加类型化接口：`WatchlistItem { id, market, code, created_at }`，并增加 `watchlist/list/add/delete` 方法；所有写入沿用集中 CSRF 和 Cookie 封装。
3. 将自选页状态变为 `{items, loading, error}`，批量粘贴时逐个调用创建接口并汇总成功/失败；重复项按后端幂等结果显示，不再写 `vr-watchlist`。
4. 允许“实时行情开关”保留在 localStorage，但股票代码来源必须来自账户 API。行情缺失显示 `—` 与来源失败状态，不显示 `0`。
5. 将每日复盘和资讯雷达的关注列表改为异步加载；未登录时保持公共页面可浏览，但不显示或读取私有关注列表。

**验收：** A 在设备 1 添加股票，B 在同一设备登录后列表为空；A 再登录时列表恢复。缺失 Cookie 为 401，缺失 CSRF 的添加/删除为 403。

### 工作包 2：持仓、笔记、研报前端闭环与旧回归测试迁移

**范围：** `backend/user_assets.py`、`backend/app.py`、`backend/tests/test_fixes.py`、`backend/tests/test_reports_and_security.py`、`frontend/src/pages/{Portfolio,Notes,MyReports}.tsx`、`frontend/src/components/ui/SaveNoteButton.tsx`、`frontend/src/pages/Debate.tsx`、`frontend/src/lib/{api,notes}.ts`。

**实施：**

1. 先写失败测试：持仓删除必须传 `holding_id`，清仓删除必须传 `position_id`；同代码的两笔持仓均保留 UUID；A/B 互相删除为 404；研报下载、删除和笔记保存均只操作当前用户。
2. 调整 `/api/portfolio` 返回契约，在既有展示字段外增加不可变 `id`；报价适配器按本次持仓代码批量获取实时行情，失败时 `price/market_value/pnl/pnl_pct` 为 `null` 且 `quote_status != complete`。成本、股数和盈亏计算保持 `Decimal`，只在 JSON 输出时转换为数字。
3. 前端持仓页调用新 UUID 删除接口；添加后重新读取持仓或消费明确的 `PortfolioData` 返回，禁止依据股票代码删除全部记录。
4. 用 API 重写笔记列表、创建、删除和“保存 AI 内容”；移除 `vr-notes` 作为主存储。历史 localStorage 不自动上传，首次进入只提示用户“历史本机笔记未迁移”。
5. 研报页继续用服务端文件接口，但在 401/404/上传失败时给出可操作提示；删除后刷新账户列表。将旧的全局 JSON API 测试改为两账户认证场景，保留旧文件模块仅作为离线备份测试。

**验收：** 后端完整测试不得再出现依赖未登录全局持仓的失败；前端可以录入两笔相同股票代码、分别删除其中一笔；跨用户报告 URL 返回 404 且不泄露文件名。

### 工作包 3：用户 AI 凭据加密、模型白名单与流式调用收口

**范围：** `backend/requirements.txt`、`backend/ai_credentials.py`、`backend/app.py`、`backend/tests/test_ai_credentials.py`、`frontend/src/pages/Settings.tsx`、`frontend/src/lib/{llm,agents,ndjson,api}.ts`、`frontend/src/lib/ai-models.ts`。

**实施：**

1. 增加 `cryptography` 受控版本，并写失败测试：数据库密文不等于 Key；列表仅返回 provider、尾缀和更新时间；A 的凭据对 B 不可见；请求体出现 `apiKey`、`baseURL` 或未白名单模型返回 422；无凭据调用返回 409。
2. `ai_credentials.py` 从 `VR_CREDENTIAL_ENCRYPTION_KEY` 读取 32 字节 URL-safe key，使用 AES-GCM、独立 nonce、`user_id:provider` associated data 加密。解密只在调用期间驻留内存。
3. 服务端白名单仅开放已配置的 StepFun `step-3.7-flash`；前端只发送 `model_id`。删除 Custom/OpenAI 任意 Base URL 和本地 CLI 配置入口，避免 SSRF 与不可审计模型来源。
4. `/api/chat`、`/api/debate`、`/api/reflect` 添加当前用户与 CSRF 依赖、最大消息条数/单条长度/总上下文限制、外部调用超时、取消传递和结构化 `AiUsageEvent`。日志只写 request_id、provider、model、耗时、token、状态、错误码。
5. 设置页仅在保存时传一次 API Key；刷新后显示掩码尾缀和删除按钮，绝不读取/回显明文。测试仅替身下游模型执行器，不调用真实模型。

**验收：** 浏览器 localStorage、网络请求和 API 响应中均不含 API Key/Base URL；同一用户保存后可用，另一用户调用为 409；自动化测试无任何付费调用。

### 工作包 4：发布前安全收口、双账户端到端验证与可观测性

**范围：** `backend/models.py`、新的 Alembic expand migration、`backend/auth.py`、`backend/tests/test_auth_api.py`、`docs/` 部署说明、前端契约测试。

**实施：**

1. 新增持久化登录限流表及迁移：以用户名规范化摘要记录有限时间窗失败次数；达到阈值后返回通用 429，不泄露账户是否存在。成功登录清除该标识的失败计数。不得修改已执行的 `20260811_01` 迁移。
2. 给认证、私有写入和 AI 调用加入 `request_id`；错误日志脱敏，不输出 Cookie、密码、Key、报告内容或持仓细节。
3. 更新 `.env.example`：生产要求 `VR_COOKIE_SECURE=true`、明确 `VR_ALLOW_ORIGINS`、随机 Session/加密密钥、`VR_REPORTS_DIR` 非仓库目录；实际 `.env` 不提交。
4. 用两个独立浏览器 Cookie Jar 执行端到端脚本：注册 A/B、写入全部私有资源、交叉访问、注销、重新登录、AI 凭据保存与删除。测试后清理测试账户与临时报告目录。
5. 执行后端全量非 live 测试、前端全部契约测试、Vite 生产构建、Alembic `current`。仅全部通过后才允许进行本地手动验收。

**发布门槛：** 四个工作包全部通过；无旧全局私有 HTTP 路由；跨账户 404、未登录 401、CSRF 403、限流 429 均有自动化证据；未发现明文 Key；生产配置检查完成。否则仅可作为本地开发版本运行。
