# Vibe-Research 后端接口清单

> 基础路径：`/api` | 端口：`8900` | 前端通过 Vite 代理 `/api` 访问
> 鉴权：`/api/auth/*` 无需登录，其余私有接口需 Cookie 会话 (`vr_session`) + CSRF Header (`X-CSRF-Token`)
> 速率限制：公开数据接口 120 req/min，chat/debate/reflect 30 req/h，注册 5 req/h，登录 10 req/15min，sector-refresh 1 req/h

---

## 一、健康与系统

### 1. `GET /api/health`
- **请求参数**：无
- **响应字段**：

| 字段 | 含义 |
|------|------|
| `ok` | 服务是否存活，布尔值 |
| `service` | 服务名，固定 `"qingshu-api"` |
| `version` | 当前版本号 |

---

### 2. `GET /api/ready`
- **请求参数**：无（需有效 Cookie）
- **响应字段**：

| 字段 | 含义 |
|------|------|
| `ok` | 全部依赖就绪则为 true |
| `service` | 服务名 |
| `version` | 版本号 |
| `sector_snapshot` | 板块快照状态（含 `ok` / `stale` / `age_seconds` 等） |
| `public_data_snapshot` | 公开数据快照状态 |

---

### 3. `GET /api/metrics`
- **说明**：Prometheus 指标端点（`include_in_schema=False`，不对外暴露文档）
- **请求参数**：无

---

## 二、认证（Auth）

### 4. `POST /api/auth/register`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `username` | 是 | 用户名，非空字符串 |
| `password` | 是 | 密码，非空字符串 |
| `phone` | 是 | 手机号，非空字符串 |

- **响应**（201 Created）：

| 字段 | 含义 |
|------|------|
| `data.id` | 新用户 ID |
| `data.username` | 用户名 |

- **Cookie 返回**：`vr_session`（HttpOnly）+ `vr_csrf`（非 HttpOnly，前端需读取用于后续请求的 CSRF Header）

---

### 5. `POST /api/auth/login`
- **请求体**（JSON）：同 register
- **响应**（200 OK）：同 register

---

### 6. `GET /api/auth/me`
- **请求参数**：无（需有效 Cookie）
- **响应**：

| 字段 | 含义 |
|------|------|
| `data.id` | 当前用户 ID |
| `data.username` | 当前用户名 |

---

### 7. `POST /api/auth/logout`
- **请求参数**：无（需 Cookie + CSRF）
- **响应**：204 No Content（无 Body）
- **副作用**：撤销当前会话，清除 Cookie

---

## 三、AI 凭据管理

### 8. `GET /api/ai/credential`
- **请求参数**：无（需有效 Cookie）
- **响应**：

| 字段 | 含义 |
|------|------|
| `data` | `ai_credentials.status_payload()` 返回值，含凭据是否存在、模型名、base_url 状态等 |

---

### 9. `PUT /api/ai/credential`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `api_key` | 是 | AI 服务 API Key |
| `base_url` | 是 | API 基础地址 |
| `model` | 是 | 模型名称 |

- **响应**：`{"data": ...}`（保存后的凭据状态，不含原始密钥）

---

### 10. `DELETE /api/ai/credential`
- **请求参数**：无（需 Cookie + CSRF）
- **响应**：204 No Content

---

## 四、AI 对话（Chat）

### 11. `POST /api/chat`
- **流式响应**：`application/x-ndjson`，每行一个事件对象
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `messages` | 是 | 对话消息数组（`role`: `user`/`assistant`，`content`: 文本），最少 1 条，最多 40 条 |
| `context` | 否 | 上下文文本（如研报内容），默认 `""`，最多 12000 字符 |
| `research_mode` | 否 | 是否启用研究模式，布尔值，默认 `false` |
| `research_question_id` | 否 | 研究问题 ID（仅 `research_mode=true` 时使用），如 `recent_events`，最多 64 字符 |
| `stock_code` | 否 | 股票代码（6 位 A 股 / 5 位基金 / 海外代码如 `AAPL`） |
| `stock_name` | 否 | 股票名称，最多 64 字符 |

- **流式事件类型**（每行一个 JSON）：
  - `{"type": "tool", ...}` — AI 调用工具
  - `{"type": "delta", ...}` — 文本增量
  - `{"type": "done", ...}` — 完成
  - `{"type": "error", "code": "...", "message": "..."}` — 错误

---

## 五、多空辩论（Debate）

### 12. `POST /api/debate`
- **流式响应**：`application/x-ndjson`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |
| `rounds` | 否 | 辩论轮数，默认 `1`，>=2 时固定为 2 |

- **流式事件**：同 chat（`tool` / `delta` / `done` / `error`）

---

## 六、反思审计（Reflection）

### 13. `POST /api/reflect`
- **流式响应**：`application/x-ndjson`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `source` | 是 | 待审计的文本内容（如分析文章），不能为空 |
| `title` | 否 | 标题，默认 `""` |

- **流式事件**：同 chat

---

## 七、资讯雷达（News Radar）

### 14. `GET /api/radar`
- **请求参数**：无
- **响应**：`{"data": ...}` — 12 赛道 RSS 资讯缓存

---

### 15. `POST /api/radar/refresh`
- **请求参数**：无
- **响应**：`{"data": ...}` — 强制刷新全部 RSS 源（耗时约 20-40s）

---

## 八、市场概览

### 16. `GET /api/market/overview`
- **请求参数**：无
- **响应**：`{"data": {...}}`
- **data 字段**（示意）：

| 字段 | 含义 |
|------|------|
| `sentiment` | 市场情绪指标 |
| `sectors` | 板块资金流数组 |

---

### 17. `GET /api/market/emotion`
- **请求参数**：无
- **响应**：`{"data": {...}}`
- **data 字段**（示意）：

| 字段 | 含义 |
|------|------|
| 连板梯队相关 | 最高连板、炸板率、封板率、晋级率、涨跌停家数 |
| 个股清单 | `code` / `name` / `连板数` 等 |

---

### 18. `GET /api/market/turnover-top`
- **请求参数**：无
- **响应**：`{"data": {"stocks": [...]}}`
- **stocks 每项字段**：

| 字段 | 含义 |
|------|------|
| `code` | 6 位代码 |
| `name` | 名称 |
| `price` | 最新价 |
| `pct` | 涨跌幅% |
| `amount` | 成交额（元） |
| `mcap` | 总市值（元） |
| `float_cap` | 流通市值（元） |
| `industry` | 所属行业 |

---

### 19. `GET /api/global/indices`
- **请求参数**：无
- **响应**：`{"data": [...]}`
- **每项字段**：`name` / `price` / `change_pct` / `change_amt`（道指 / 标普500 / 纳斯达克 / 恒生 / 恒生科技）

---

## 九、全球个股（美股 / 港股）

### 20. `GET /api/global/stock`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `symbol` | 是 | 代码，如 `AAPL` / `BABA` / `00700`，1-16 字符 |

- **响应**：`{"data": {...}}`
- **data 字段**（由 `gstock.us_hk_stock` 返回，含行情 + 关键财务指标）

---

### 21. `GET /api/global/hk/cashflow`
- **请求参数**：同 `/api/global/stock`
- **响应**：`{"data": {...}}` — 港股现金流量表

---

## 十、A 股实时行情

### 22. `GET /api/indices`
- **请求参数**：无
- **响应**：`{"data": [...]}` — 上证 / 深证成指 / 创业板指 / 沪深300 实时行情
- **每项字段**：`name` / `price` / `change_pct` / `change_amt`

---

### 23. `GET /api/quote`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `codes` | 是 | 逗号分隔的 6 位代码，如 `000001,600519` |

- **响应**：`{"data": {"000001": {...}, "600519": {...}}}`
- **每只股票字段**：

| 字段 | 含义 |
|------|------|
| `name` | 名称 |
| `price` | 现价 |
| `last_close` | 昨收 |
| `open` | 开盘价 |
| `change_amt` | 涨跌额 |
| `change_pct` | 涨跌幅% |
| `high` | 最高 |
| `low` | 最低 |
| `amount_wan` | 成交额（万元） |
| `turnover_pct` | 换手率% |
| `pe_ttm` | 市盈率 TTM |
| `amplitude_pct` | 振幅% |
| `mcap_yi` | 总市值（亿元） |
| `float_mcap_yi` | 流通市值（亿元） |
| `pb` | 市净率 |
| `limit_up` | 涨停价 |
| `limit_down` | 跌停价 |
| `vol_ratio` | 量比 |
| `pe_static` | 静态市盈率 |

---

### 24. `GET /api/market/index-candles`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `symbols` | 是 | 逗号分隔的指数标识符，1-10 个，如 `SH000001,SZ399001` |
| `period` | 否 | 周期，默认 `"1d"`（仅支持日线） |
| `limit` | 否 | 返回条数，默认 60，范围 20-250 |

- **响应**：`{"data": {...}}` — 指数 K 线序列

---

## 十一、估值与财务

### 25. `GET /api/valuation`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |

- **响应**：`{"data": {...}}`
- **data 字段**：

| 字段 | 含义 |
|------|------|
| `name` | 名称 |
| `code` | 代码 |
| `price` | 现价 |
| `mcap_yi` | 总市值（亿元） |
| `pe_ttm` | PE-TTM |
| `pb` | PB |
| `eps_26e` | 2026E EPS |
| `eps_27e` | 2027E EPS |
| `pe_26e` | 2026E PE |
| `cagr_pct` | EPS 复合增长率% |
| `peg` | PEG |
| `digest_years` | PE 消化年数 |
| `analyst_count` | 预测机构数 |
| `forecast_note` | 一致预期获取失败时的说明 |

---

### 26. `GET /api/valuation/percentile`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |

- **响应**：`{"data": {"period": "近5年", "metrics": {...}}}`
- **metrics 每项**（`pe_ttm` / `pb`）：

| 字段 | 含义 |
|------|------|
| `current` | 当前值 |
| `percentile` | 历史分位% |
| `min` | 最小值 |
| `max` | 最大值 |
| `p20` | 20 分位 |
| `p50` | 50 分位 |
| `p80` | 80 分位 |
| `n` | 样本数 |

---

### 27. `GET /api/financials`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |

- **响应**：`{"data": {...}}`
- **data 字段**（同花顺财务摘要，最新报告期）：

| 字段 | 含义 |
|------|------|
| `period` | 报告期 |
| `revenue` | 营业总收入 |
| `revenue_yoy` | 营收同比增长率% |
| `net_profit` | 净利润 |
| `net_profit_yoy` | 净利润同比增长率% |
| `eps` | 基本每股收益 |
| `bvps` | 每股净资产 |
| `roe` | 净资产收益率% |
| `gross_margin` | 销售毛利率% |
| `net_margin` | 销售净利率% |
| `op_cf_ps` | 每股经营现金流 |

---

### 28. `GET /api/finance`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |

- **响应**：`{"data": {...}}` — mootdx 季报财务快照（约 37 个字段，随 mootdx 返回）

---

## 十二、公告与研报

### 29. `GET /api/announcements`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |

- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `date` | 公告日期（YYYY-MM-DD） |
| `title` | 标题 |
| `type` | 类型 |
| `url` | 详情链接（东财） |

---

### 30. `GET /api/disclosure`
- **请求参数**：同 announcements
- **响应**：`{"data": [...]}` — 巨潮公告全文列表（字段随 akshare 返回）

---

### 31. `GET /api/reports`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |
| `pages` | 否 | 翻页数，默认 2，范围 1-5 |

- **响应**：`{"data": [...]}` — 东财个股研报列表
- **每项字段**：东财原始字段 + `pdfUrl`（研报 PDF 链接）

---

### 32. `GET /api/news`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |
| `limit` | 否 | 条数，默认 20，范围 1-50 |

- **响应**：`{"data": [...]}` — 个股新闻（字段随 akshare 返回）

---

## 十三、K 线与技术

### 33. `GET /api/kline`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |
| `category` | 否 | K 线周期：4=日线，5=周线，6=月线，11=60 分钟，默认 4 |
| `offset` | 否 | 返回条数，默认 60，范围 1-800 |

- **响应**：`{"data": [...]}` — K 线 OHLCV 数组（字段随 mootdx 返回）

---

## 十四、资金面与筹码

### 34. `GET /api/margin`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 6 位 A 股代码 |

- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `date` | 日期 |
| `rzye` | 融资余额 |
| `rzmre` | 融资买入额 |
| `rzche` | 融资偿还额 |
| `rqye` | 融券余额 |
| `rqmcl` | 融券卖出量 |
| `rzrqye` | 两融合计余额 |

---

### 35. `GET /api/block-trade`
- **请求参数**：同 margin
- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `date` | 日期 |
| `price` | 成交价 |
| `close` | 收盘价 |
| `premium_pct` | 折溢价率% |
| `vol` | 成交量 |
| `amount` | 成交额 |
| `buyer` | 买方营业部 |
| `seller` | 卖方营业部 |

---

### 36. `GET /api/holders`
- **请求参数**：同 margin
- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `date` | 截止日期 |
| `holder_num` | 股东户数 |
| `change_ratio` | 环比变化率 |
| `avg_shares` | 户均持股 |

---

### 37. `GET /api/dividend`
- **请求参数**：同 margin
- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `date` | 除权除息日 |
| `bonus_rmb` | 每股派息（税前，元） |
| `transfer_ratio` | 每 10 股转增 |
| `bonus_ratio` | 每 10 股送股 |
| `plan` | 进度 |

---

### 38. `GET /api/fund-flow`
- **请求参数**：同 margin
- **响应**：`{"data": [...]}`
- **每项字段**（最近 120 交易日，日级）：

| 字段 | 含义 |
|------|------|
| `date` | 日期 |
| `main_net` | 主力净流入（元） |
| `small_net` | 小单净流入 |
| `mid_net` | 中单净流入 |
| `large_net` | 大单净流入 |
| `super_net` | 超大单净流入 |

---

### 39. `GET /api/dragon-tiger`
- **请求参数**：同 margin
- **响应**：`{"data": {"records": [...], "seats": {...}, "institution": {...}}}`
- **records 每项字段**：

| 字段 | 含义 |
|------|------|
| `date` | 上榜日期 |
| `reason` | 上榜原因 |
| `net_buy` | 净买入（万元） |
| `turnover` | 换手率% |

- **seats**：

| 字段 | 含义 |
|------|------|
| `seats.buy[].name` | 买方营业部名 |
| `seats.buy[].buy_amt` | 买入额（万元） |
| `seats.buy[].sell_amt` | 卖出额（万元） |
| `seats.buy[].net` | 净额（万元） |
| `seats.sell[].name` | 卖方营业部名 |
| `seats.sell[].buy_amt` | 买入额 |
| `seats.sell[].sell_amt` | 卖出额 |
| `seats.sell[].net` | 净额 |

- **institution**：

| 字段 | 含义 |
|------|------|
| `institution.buy_amt` | 机构席位买入额（万元） |
| `institution.sell_amt` | 机构席位卖出额 |
| `institution.net_amt` | 机构席位净额 |

---

### 40. `GET /api/lockup`
- **请求参数**：同 margin
- **响应**：`{"data": {"history": [...], "upcoming": [...]}}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `date` | 解禁日期 |
| `type` | 股份类型 |
| `shares` | 解禁股数 |
| `able_shares` | 实际可流通股数 |
| `ratio` | 解禁比例 |

---

### 41. `GET /api/blocks`
- **请求参数**：同 margin
- **响应**：`{"data": {...}}` — 个股所属板块/概念归属

---

### 42. `GET /api/hot-concepts`
- **请求参数**：同 margin
- **响应**：`{"data": [...]}` — 个股被归到的热门概念

---

### 43. `GET /api/investor-qa`
- **请求参数**：同 margin
- **响应**：`{"data": [...]}` — 互动易问答（投资者提问 + 公司回复）

---

## 十五、行业与板块

### 44. `GET /api/industry`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `top` | 否 | 返回行业数量，默认 20，范围 5-50 |

- **响应**：`{"data": [...]}` — 全行业涨跌幅排名（板块级，无个股名单）

---

### 45. `GET /api/all-sectors`
- **请求参数**：无
- **响应**：`{"data": {"industries": [...], "concepts": [...], "stale": bool, "age_seconds": num, ...}}`
- **sector 每项字段**（industry / concept 通用）：

| 字段 | 含义 |
|------|------|
| `kind` | `"行业"` 或 `"概念"` |
| `code` | 板块代码 |
| `name` | 板块名称 |
| `pct_change` | 涨跌幅% |

---

### 46. `GET /api/sector-members`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `kind` | 是 | 板块类型，`"行业"` 或 `"概念"` |
| `code` | 是 | 板块代码 |

- **响应**：`{"data": {"kind": ..., "code": ..., "snapshot_id": ..., "as_of": ..., "source": ..., "members": [...]}}`

---

### 47. `GET /api/sector-detail`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `kind` | 是 | 板块类型 |
| `code` | 是 | 板块代码 |

- **响应**：`{"data": {...}}` — 板块日线详情（字段同 all-sectors 中的单条 + `snapshot_id` / `retrieved_at` / `method_version`）

---

### 48. `GET /api/sectors/status`
- **请求参数**：无
- **响应**：`{"data": {...}}` — 板块刷新服务状态

---

### 49. `POST /api/sectors/refresh`
- **请求参数**：无（需 Cookie + CSRF）
- **响应**（202 Accepted）：`{"data": {...}}` — 触发板块快照异步刷新

---

## 十六、搜索

### 50. `GET /api/stocks/search`
- **请求参数**：

| 字段 | 必填 | 含义 |
|------|------|------|
| `query` | 是 | 搜索关键词（代码或名称），2-32 字符 |
| `limit` | 否 | 返回条数，默认 20，范围 1-50 |

- **响应**：`{"data": {"query": ..., "source": "TeaJoin/Tushare stock_basic", "results": [...]}}`
- **results 每项字段**（随 TeaJoin 返回，含 code / name / market 等）

---

## 十七、个人资产（需登录）

### 51. `GET /api/watchlist`
- **请求参数**：无（需 Cookie）
- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `id` | 自选股记录 ID |
| `market` | 市场（`sh` / `sz` / `bj`） |
| `code` | 6 位代码 |
| `created_at` | 添加时间（ISO 8601） |

---

### 52. `POST /api/watchlist`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 股票代码 |

- **响应**（201 Created）：`{"data": {...}}` — 同 watchlist GET 单条结构

---

### 53. `DELETE /api/watchlist/{item_id}`
- **路径参数**：`item_id` — 自选股记录 ID
- **请求参数**：无（需 Cookie + CSRF）
- **响应**：204 No Content

---

### 54. `GET /api/portfolio`
- **请求参数**：无（需 Cookie）
- **响应**：`{"data": {...}}`
- **data 字段**：

| 字段 | 含义 |
|------|------|
| `holdings` | 当前持仓数组 |
| `holdings[].id` | 持仓 ID |
| `holdings[].market` | 市场 |
| `holdings[].code` | 代码 |
| `holdings[].name` | 名称 |
| `holdings[].price` | 最新价 |
| `holdings[].shares` | 持有股数 |
| `holdings[].cost` | 成本价 |
| `holdings[].market_value` | 市值 |
| `holdings[].pnl` | 浮动盈亏（元） |
| `holdings[].pnl_pct` | 浮动盈亏% |
| `holdings[].quote_status` | 行情状态（`available` / `quote_missing` / `source_unavailable`） |
| `totals.market_value` | 总市值 |
| `totals.cost` | 总成本 |
| `totals.pnl` | 总浮动盈亏 |
| `totals.pnl_pct` | 总浮动盈亏% |
| `closed` | 已清仓数组 |
| `closed[].id` | 清仓记录 ID |
| `closed[].market` | 市场 |
| `closed[].code` | 代码 |
| `closed[].name` | 名称 |
| `closed[].date` | 清仓日期 |
| `closed[].price` | 清仓价 |
| `closed[].shares` | 清仓股数 |
| `closed[].cost` | 成本价 |
| `closed[].pnl` | 已实现盈亏 |
| `closed[].pnl_pct` | 已实现盈亏% |
| `realized_pnl` | 累计已实现盈亏 |
| `updated` | 更新时间（ISO 8601） |
| `last_refresh` | 行情刷新时间 |

---

### 55. `POST /api/portfolio/holding`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 股票代码 |
| `shares` | 是 | 股数，必须 > 0 |
| `cost` | 是 | 成本价 |

- **响应**（201 Created）：`{"data": {...}}` — 新建持仓行（同 portfolio holdings 单条结构，price 为 null）

---

### 56. `DELETE /api/portfolio/holding/{holding_id}`
- **路径参数**：`holding_id`
- **响应**：204 No Content

---

### 57. `POST /api/portfolio/close`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `code` | 是 | 股票代码 |
| `date` | 是 | 清仓日期，格式 `YYYY-MM-DD` |
| `price` | 是 | 清仓价，必须 > 0 |
| `shares` | 是 | 清仓股数，必须 > 0 |
| `cost` | 是 | 成本价 |

- **响应**（201 Created）：`{"data": {...}}` — 已清仓记录（同 portfolio closed 单条结构）

---

### 58. `DELETE /api/portfolio/close/{position_id}`
- **路径参数**：`position_id`
- **响应**：204 No Content

---

## 十八、研究笔记（Notes）

### 59. `GET /api/notes`
- **请求参数**：无（需 Cookie）
- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `id` | 笔记 ID |
| `kind` | 类型，默认 `"general"`，最多 64 字符 |
| `title` | 标题 |
| `content` | 内容 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

---

### 60. `POST /api/notes`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `kind` | 否 | 类型，默认 `"general"` |
| `title` | 是 | 标题，非空 |
| `content` | 是 | 内容，非空 |

- **响应**（201 Created）：`{"data": {...}}` — 同 notes GET 单条结构

---

### 61. `DELETE /api/notes/{note_id}`
- **路径参数**：`note_id`
- **响应**：204 No Content

---

## 十九、我的研报（My Reports）

### 62. `GET /api/myreports`
- **请求参数**：无（需 Cookie）
- **响应**：`{"data": [...]}`
- **每项字段**：

| 字段 | 含义 |
|------|------|
| `id` | 报告 ID |
| `name` | 原始文件名 |
| `size` | 文件大小（字节） |
| `ext` | 文件扩展名 |
| `ts` | 上传时间戳（毫秒） |
| `mime_type` | MIME 类型 |
| `industry` | 行业标签（当前固定 `"未分类"`） |

---

### 63. `POST /api/myreports`
- **请求体**（JSON）：

| 字段 | 必填 | 含义 |
|------|------|------|
| `name` | 是 | 文件名（含扩展名） |
| `content_b64` | 是 | 文件 base64 内容（支持 `data:` URI 前缀） |

- **限制**：最大 25MB，允许扩展名：`.pdf` `.doc` `.docx` `.txt` `.md` `.csv` `.xls` `.xlsx` `.ppt` `.pptx` `.png` `.jpg` `.jpeg` `.webp`
- **响应**（201 Created）：`{"data": {...}}` — 同 myreports GET 单条结构

---

### 64. `GET /api/myreports/file/{report_id}`
- **路径参数**：`report_id`
- **响应**：文件流（`FileResponse`），Content-Disposition 使用原始文件名

---

### 65. `DELETE /api/myreports/{report_id}`
- **路径参数**：`report_id`
- **响应**：204 No Content

---

## 二十、旧接口（已停用，返回 410）

以下旧全局接口全部返回 `HTTP 410 Gone`，仅作记录：

| 方法 | 路径 | 原功能 |
|------|------|--------|
| GET | `/api/_legacy_disabled/portfolio` | 旧全局持仓 |
| POST | `/api/_legacy_disabled/portfolio/holding` | 旧加持仓 |
| DELETE | `/api/_legacy_disabled/portfolio/holding` | 旧删持仓 |
| POST | `/api/_legacy_disabled/portfolio/close` | 旧清仓 |
| DELETE | `/api/_legacy_disabled/portfolio/close` | 旧删清仓 |
| POST | `/api/_legacy_disabled/portfolio/refresh` | 旧刷新持仓 |
| GET | `/api/_legacy_disabled/myreports` | 旧全局研报列表 |
| POST | `/api/_legacy_disabled/myreports` | 旧全局研报上传 |
| GET | `/api/_legacy_disabled/myreports/file/{rid}` | 旧研报下载 |
| DELETE | `/api/_legacy_disabled/myreports/{rid}` | 旧研报删除 |

---

## 二十一、研究模式（Research Mode）

研究模式通过 `POST /api/chat` 的 `research_mode=true` + `research_question_id` 启用，后端不暴露独立端点。可用研究问题 ID 如下：

| `research_question_id` | 标签 | 能力等级 |
|------------------------|------|----------|
| `recent_events` | 最近发生了什么？ | PARTIALLY_SUPPORTED |
| `latest_earnings` | 最新财报验证了什么？ | PARTIALLY_SUPPORTED |
| `growth_earnings` | 增长与利润弹性 | PARTIALLY_SUPPORTED |
| `expectations_gap` | 市场预期与预期差 | NOT_SUPPORTED |
| `valuation_framework` | 估值与定价框架 | PARTIALLY_SUPPORTED |
| `business_model` | 公司怎么赚钱？ | PARTIALLY_SUPPORTED |
| `price_move_attribution` | 近期异动归因 | PARTIALLY_SUPPORTED |
| `earnings_quality` | 盈利质量 | PARTIALLY_SUPPORTED |
| `cash_flow_capital_allocation` | 现金流与资本配置 | PARTIALLY_SUPPORTED |
| `industry_cycle` | 行业景气与周期 | PARTIALLY_SUPPORTED |
| `competitive_value_capture` | 竞争格局与价值捕获 | PARTIALLY_SUPPORTED |
| `risks_falsification` | 风险与证伪 | PARTIALLY_SUPPORTED |

---

## 汇总：接口清单一览

| # | 路径 | 方法 | 鉴权 | 流式 | 说明 |
|---|------|------|------|------|------|
| 1 | `/api/health` | GET | 否 | 否 | 存活检查 |
| 2 | `/api/ready` | GET | 是 | 否 | 依赖就绪检查 |
| 3 | `/api/metrics` | GET | 否 | 否 | Prometheus 指标 |
| 4 | `/api/auth/register` | POST | 否 | 否 | 注册 |
| 5 | `/api/auth/login` | POST | 否 | 否 | 登录 |
| 6 | `/api/auth/me` | GET | 是 | 否 | 当前用户 |
| 7 | `/api/auth/logout` | POST | 是 | 否 | 登出 |
| 8 | `/api/ai/credential` | GET | 是 | 否 | AI 凭据状态 |
| 9 | `/api/ai/credential` | PUT | 是 | 否 | 保存 AI 凭据 |
| 10 | `/api/ai/credential` | DELETE | 是 | 否 | 删除 AI 凭据 |
| 11 | `/api/chat` | POST | 是 | **是** | AI 对话 |
| 12 | `/api/debate` | POST | 是 | **是** | 多空辩论 |
| 13 | `/api/reflect` | POST | 是 | **是** | 反思审计 |
| 14 | `/api/radar` | GET | 否 | 否 | 资讯雷达 |
| 15 | `/api/radar/refresh` | POST | 否 | 否 | 刷新资讯雷达 |
| 16 | `/api/market/overview` | GET | 否 | 否 | 市场概览 |
| 17 | `/api/market/emotion` | GET | 否 | 否 | 短线情绪 |
| 18 | `/api/market/turnover-top` | GET | 否 | 否 | 成交额榜 |
| 19 | `/api/global/indices` | GET | 否 | 否 | 全球指数 |
| 20 | `/api/global/stock` | GET | 否 | 否 | 美股/港股个股 |
| 21 | `/api/global/hk/cashflow` | GET | 否 | 否 | 港股现金流 |
| 22 | `/api/indices` | GET | 否 | 否 | A 股大盘指数 |
| 23 | `/api/quote` | GET | 否 | 否 | 实时行情 |
| 24 | `/api/market/index-candles` | GET | 否 | 否 | 指数 K 线 |
| 25 | `/api/valuation` | GET | 否 | 否 | 完整估值 |
| 26 | `/api/valuation/percentile` | GET | 否 | 否 | 估值分位 |
| 27 | `/api/financials` | GET | 否 | 否 | 财务摘要 |
| 28 | `/api/finance` | GET | 否 | 否 | 季报财务 |
| 29 | `/api/announcements` | GET | 否 | 否 | 个股公告 |
| 30 | `/api/disclosure` | GET | 否 | 否 | 巨潮公告 |
| 31 | `/api/reports` | GET | 否 | 否 | 个股研报 |
| 32 | `/api/news` | GET | 否 | 否 | 个股新闻 |
| 33 | `/api/kline` | GET | 否 | 否 | K 线 |
| 34 | `/api/margin` | GET | 否 | 否 | 融资融券 |
| 35 | `/api/block-trade` | GET | 否 | 否 | 大宗交易 |
| 36 | `/api/holders` | GET | 否 | 否 | 股东户数 |
| 37 | `/api/dividend` | GET | 否 | 否 | 分红记录 |
| 38 | `/api/fund-flow` | GET | 否 | 否 | 资金流向 |
| 39 | `/api/dragon-tiger` | GET | 否 | 否 | 龙虎榜 |
| 40 | `/api/lockup` | GET | 否 | 否 | 限售解禁 |
| 41 | `/api/blocks` | GET | 否 | 否 | 板块归属 |
| 42 | `/api/hot-concepts` | GET | 否 | 否 | 热门概念 |
| 43 | `/api/investor-qa` | GET | 否 | 否 | 互动易问答 |
| 44 | `/api/industry` | GET | 否 | 否 | 行业排名 |
| 45 | `/api/all-sectors` | GET | 否 | 否 | 全板块快照 |
| 46 | `/api/sector-members` | GET | 否 | 否 | 板块成分股 |
| 47 | `/api/sector-detail` | GET | 否 | 否 | 板块日线详情 |
| 48 | `/api/sectors/status` | GET | 否 | 否 | 板块刷新状态 |
| 49 | `/api/sectors/refresh` | POST | 是 | 否 | 触发板块刷新 |
| 50 | `/api/stocks/search` | GET | 否 | 否 | 股票搜索 |
| 51 | `/api/watchlist` | GET | 是 | 否 | 自选股列表 |
| 52 | `/api/watchlist` | POST | 是 | 否 | 加自选股 |
| 53 | `/api/watchlist/{item_id}` | DELETE | 是 | 否 | 删自选股 |
| 54 | `/api/portfolio` | GET | 是 | 否 | 持仓总览 |
| 55 | `/api/portfolio/holding` | POST | 是 | 否 | 加持仓 |
| 56 | `/api/portfolio/holding/{holding_id}` | DELETE | 是 | 否 | 删持仓 |
| 57 | `/api/portfolio/close` | POST | 是 | 否 | 记清仓 |
| 58 | `/api/portfolio/close/{position_id}` | DELETE | 是 | 否 | 删清仓 |
| 59 | `/api/notes` | GET | 是 | 否 | 笔记列表 |
| 60 | `/api/notes` | POST | 是 | 否 | 创建笔记 |
| 61 | `/api/notes/{note_id}` | DELETE | 是 | 否 | 删除笔记 |
| 62 | `/api/myreports` | GET | 是 | 否 | 研报列表 |
| 63 | `/api/myreports` | POST | 是 | 否 | 上传研报 |
| 64 | `/api/myreports/file/{report_id}` | GET | 是 | 否 | 下载研报 |
| 65 | `/api/myreports/{report_id}` | DELETE | 是 | 否 | 删除研报 |

**合计：有效接口 65 个（不含旧停用接口），其中流式接口 3 个（chat / debate / reflect），需登录接口 22 个，完全公开接口 40 个。**
