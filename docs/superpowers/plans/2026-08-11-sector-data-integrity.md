# 板块数据口径修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一板块列表、分类和成分股的供应商代码体系，防止错配，并明确非实时数据口径。

**Architecture:** 列表和成分股都使用 TeaJoin/Tushare 的同花顺指数体系：`ths_index.type=I` 为行业、`type=N` 为概念；成分统一经 `ths_member(ts_code)` 获取。页面不再拼接新浪/akshare 行情，也不将无实时授权的数据标为实时。

**Tech Stack:** FastAPI、Python requests、React 19、TypeScript、pytest、Node test runner。

## Global Constraints

- 禁止将不同供应商的板块代码、板块分类和行情混用。
- `I` 与 `N` 以外的同花顺指数不得混入行业/概念板块中心。
- TeaJoin 通用套餐不含实时行情；`change_pct`、上涨/下跌家数必须为 `null`，UI 显示数据口径而非伪实时数值。

### Task 1: 统一后端板块主数据与成分契约

**Files:** `backend/astock.py`, `backend/app.py`, `backend/tests/test_api.py`

- [ ] 写失败测试：仅保留 `I/N` 类型，保留完整 `ts_code`，禁止跨分类代码查询成分。
- [ ] 运行目标测试并确认当前混源实现失败。
- [ ] 实现 TeaJoin 同源列表、10 分钟缓存和分类校验；将上游故障映射为明确 HTTP 错误。
- [ ] 运行后端测试与 TeaJoin 实际冒烟请求。

### Task 2: 更正前端金融口径和成分呈现

**Files:** `frontend/src/lib/api.ts`, `frontend/src/pages/Sectors.tsx`, `frontend/src/pages/SectorDetail.tsx`, `frontend/tests/sector-data-contract.test.mjs`

- [ ] 写失败测试：前端类型允许 `null` 行情字段，并显示 TeaJoin 数据来源与非实时口径。
- [ ] 实现列表/详情的数据来源、更新时间说明和可点击成分股。
- [ ] 运行所有前端测试和生产构建。

### Task 3: 端到端数据一致性验证

**Files:** 无新增生产文件。

- [ ] 以一个 `I` 行业和一个 `N` 概念请求列表、详情和成分股，验证 code、name、kind 和成员返回来自同一体系。
- [ ] 运行非 live 后端全量回归、前端全量测试与构建。
