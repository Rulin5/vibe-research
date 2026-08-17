// 清数智算 后端 API 客户端。/api → vite 代理到本地 FastAPI（默认 8900）。
// 后端未启动或数据源异常时抛 ApiError，页面据此优雅降级。

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "request_failed") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export interface AuthUser { id: string; username: string; }

function csrfToken(): string {
  return document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("vr_csrf="))?.slice("vr_csrf=".length) || "";
}

export interface MyReport {
  id: string; name: string; industry: string; size: number; ext: string; ts: number;
}

export interface WatchlistItem {
  id: string; market: string; code: string; created_at: string;
}
export interface AiCredentialStatus {
  configured: boolean; active_source: "system" | "user" | "none"; provider: string; base_url: string; model: string; key_suffix: string | null;
}

// 下载/预览研报：fetch → blob → 触发浏览器下载。
export async function downloadReport(id: string, name: string): Promise<void> {
  const resp = await fetch(`/api/myreports/file/${id}`, { credentials: "include" });
  if (!resp.ok) throw new ApiError(`下载失败 HTTP ${resp.status}`, resp.status);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function request<T>(path: string, method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE" = "GET", body?: unknown): Promise<T> {
  let resp: Response;
  const opts: RequestInit = { method, credentials: "include" };
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) headers["X-CSRF-Token"] = csrfToken();
  if (Object.keys(headers).length) opts.headers = headers;
  try {
    resp = await fetch(`/api${path}`, opts);
  } catch {
    throw new ApiError("连接不到后端，请先启动 backend（uvicorn app:app --port 8900）", 0);
  }
  let payload: any = null;
  try {
    payload = await resp.json();
  } catch {
    /* 非 JSON 响应 */
  }
  if (!resp.ok) {
    throw new ApiError(payload?.detail || `HTTP ${resp.status}`, resp.status);
  }
  return (payload?.data ?? payload) as T;
}

const get = <T>(path: string) => request<T>(path, "GET");

export interface Quote {
  name: string; price: number; last_close: number; change_pct: number;
  pe_ttm: number; pb: number; mcap_yi: number; turnover_pct: number;
  limit_up: number; limit_down: number;
}

export interface Valuation {
  name: string; code: string; price: number; mcap_yi: number;
  pe_ttm: number; pb: number;
  eps_26e: number | null; eps_27e: number | null; pe_26e: number | null;
  cagr_pct: number | null; peg: number | null; digest_years: number | null;
  analyst_count: number; forecast_note?: string;
}

export interface Report {
  title: string; publishDate: string; orgSName: string;
  emRatingName?: string; indvInduName?: string; pdfUrl?: string | null;
}

export interface ValMetric {
  current: number; percentile: number; min: number; max: number;
  p20: number; p50: number; p80: number; n: number;
}
export interface ValPercentile {
  period: string; metrics: { pe_ttm?: ValMetric; pb?: ValMetric };
}

export interface Announcement {
  date: string; title: string; type: string; url: string;
}

export interface Financials {
  period: string | null;
  revenue: string | null; revenue_yoy: string | null;
  net_profit: string | null; net_profit_yoy: string | null;
  eps: string | null; bvps: string | null; roe: string | null;
  gross_margin: string | null; net_margin: string | null; op_cf_ps: string | null;
}

export interface NewsItem {
  新闻标题?: string; 发布时间?: string; 文章来源?: string; 新闻链接?: string;
}

export interface IndexQuote {
  name: string; price: number; change_pct: number; change_amt: number;
}

export interface IndexCandle {
  trade_date: string; open: number; high: number; low: number; close: number;
  pre_close: number | null; change: number | null; pct_chg: number | null;
  volume: number | null; amount: number | null; is_partial: boolean;
}
export interface IndexSeries {
  symbol: string; vendor_symbol: string; name: string; market: string; exchange: string;
  currency: string; timezone: string; frequency: "1d"; adjustment: "none";
  source: string; source_api: string; retrieved_at: string; quote_at: null; as_of: string | null;
  volume_unit: string | null; amount_unit: string;
  data_status: "fresh" | "source_unavailable" | "historical"; status_reason: string | null; realtime_available: false;
  market_session: "pre_open" | "trading" | "lunch_break" | "closed" | "closed_day" | "local_market";
  candles: IndexCandle[];
}

export interface MarketSentiment {
  up: number; down: number; flat: number; zt: number; zt_real: number; dt: number; dt_real: number;
  active: string; breadth: string; speculation: string; date: string;
}
export interface SectorFlow {
  name: string; pct: number; net: number; inflow: number; outflow: number; firms: number; amount_unit: "100m_CNY";
}
export interface MarketOverview {
  sentiment: MarketSentiment; sectors: SectorFlow[]; updated: string;
}

// 短线情绪：连板梯队 / 最高连板 / 炸板率 / 封板率 / 晋级率 / 涨跌停家数 + 连板股清单（客观公开榜单）
export interface EmotionTier { boards: number; count: number; plus: boolean }
export interface LianbanStock {
  code: string; name: string; boards: number;
  price: number; pct: number; amount: number | null; float_cap: number | null; industry: string;
}
export interface ShortTermEmotion {
  date: string;
  zt_count: number; dt_count: number; zb_count: number;
  max_boards: number; lianban_count: number;
  ladder: EmotionTier[];
  lianban_stocks: LianbanStock[];
  seal_rate: number | null; break_rate: number | null; promotion_rate: number | null;
  yzt_count: number;
}

// 全市场成交额榜（客观公开榜单）
export interface TurnoverStock {
  code: string; name: string;
  price: number | null; pct: number | null;
  amount: number | null; mcap: number | null; float_cap: number | null; industry: string;
}
export interface TurnoverTop { stocks: TurnoverStock[]; updated: string }

export interface RadarItem {
  title: string; url: string; time: string; source: string; summary?: string; zh?: string;
}
export interface Industry {
  key: string; name: string; accent: string; total: number; items: RadarItem[];
}
export interface RadarData {
  generated_at: string | null; recent_days: number; industries: Industry[];
  stats: { industries: number; total_sources: number; failed_sources?: number };
}

export interface Holding {
  id: string; market: string; code: string; name: string; quote_status: "available" | "quote_missing" | "source_unavailable" | "unavailable";
  price: number | null; shares: number; cost: number;
  market_value: number | null; pnl: number | null; pnl_pct: number | null;
}
export interface ClosedPosition {
  id: string; market: string; code: string; name: string; date: string; price: number; shares: number; cost: number;
  pnl: number; pnl_pct: number | null;
}
export interface PortfolioData {
  holdings: Holding[];
  totals: { market_value: number | null; cost: number; pnl: number | null; pnl_pct: number | null };
  closed: ClosedPosition[];
  realized_pnl: number;
  updated: string; last_refresh: string | null;
}
export interface ResearchNote {
  id: string; kind: string; title: string; content: string; created_at: string; updated_at: string;
}

// 资金面 / 筹码 / 信号（v3.3 并入，均为「用户查的那只股」的公开数据）
export interface MarginRow { date: string; rzye: number; rzmre: number; rzche: number; rqye: number; rqmcl: number; rzrqye: number }
export interface BlockTradeRow { date: string; price: number; close: number; premium_pct: number | null; vol: number; amount: number; buyer: string; seller: string }
export interface HolderRow { date: string; holder_num: number; change_ratio: number; avg_shares: number }
export interface DividendRow { date: string; bonus_rmb: number; transfer_ratio: number; bonus_ratio: number | null; plan: string }
export interface FundFlowRow { date: string; main_net: number; small_net: number; mid_net: number; large_net: number; super_net: number }
export interface DtSeat { name: string; buy_amt: number; sell_amt: number; net: number }
export interface DragonTiger {
  records: { date: string; reason: string; net_buy: number; turnover: number }[];
  seats: { buy: DtSeat[]; sell: DtSeat[] };
  institution: { buy_amt: number; sell_amt: number; net_amt: number };
}
export interface LockupRow { date: string; type: string; shares: number; able_shares: number; ratio: number }
export interface Lockup { history: LockupRow[]; upcoming: LockupRow[] }
export interface Board { name: string; code: string; change_pct: number | string; lead_stock: string }
export interface Blocks { total: number; boards: Board[]; concept_tags: string[] }
export interface HotConcept { concept: string; bk: string; hit: number }
export interface QaRow { company: string; question: string; answer: string | null; answerer: string; ask_time: string }
export interface IndustryRow { rank: number; name: string; change_pct: number; code: string; up_count: number; down_count: number }
export interface IndustryData { top: IndustryRow[]; bottom: IndustryRow[]; total: number }
export interface SectorBoard {
  code: string; name: string; kind: "行业" | "概念";
  close: number; pct_change: number; member_count: number; lead_stock: string; net_amount: number;
  provider_member_count?: number;
  as_of: string; data_status: "complete"; source?: string; source_api?: string;
  snapshot_id?: string; retrieved_at?: string; method_version?: string;
}
export interface SectorCompleteness {
  candidate_count: number; published_count: number; excluded_count: number;
  excluded_by_reason?: Record<string, number>; member_count_mismatch_count?: number;
  reused_member_sector_count?: number;
}
export interface AllSectorsData {
  industries: SectorBoard[]; concepts: SectorBoard[]; source: string; as_of: string;
  snapshot_id: string; retrieved_at: string; market: string; currency: string; timezone: string;
  frequency: string; method_version: string; completeness: SectorCompleteness;
  stale: boolean; age_seconds: number | null;
}
export interface SectorMember { code: string; name: string; market: string; joined_at: string }
export interface SectorMembers { kind: string; code: string; source: string; snapshot_id: string; as_of: string; members: SectorMember[] }
export interface SectorRefreshStatus { task_id?: string; status: "idle" | "pending" | "running" | "completed" | "failed"; current_step?: string; data_date?: string; error_detail?: string; snapshot_id?: string }
export interface StockSearchResult { code: string; ts_code: string; name: string; market: string; industry: string }
export interface StockSearch { query: string; source: string; results: StockSearchResult[] }

// 全球市场（美股 / 港股，移植自 global-stock-data · 东财域内源）
export interface GlobalIndex {
  key: string; name: string; region: string;
  price: number | null; change_pct: number | null;
}
export interface GlobalQuote {
  code: string; name: string;
  price: number | null; open: number | null; high: number | null; low: number | null;
  prev_close: number | null; amount: number | null; mcap: number | null; change_pct: number | null;
}
export interface GlobalMetrics {
  report_date: string;
  revenue: number | null; revenue_yoy: number | null; net_profit: number | null;
  eps: number | null; roe: number | null; gross_margin: number | null;
  net_margin: number | null; debt_ratio: number | null;
}
export interface GlobalStock {
  code: string; name: string; market: string;
  quote: GlobalQuote; metrics: GlobalMetrics | null;
}
export interface HkCashflowItem { amount: number | null; yoy: number | null }
export interface HkCashflowPeriod {
  report_date: string; report: string | null;
  currency: string | null; account_standard: string | null;
  items: Record<string, HkCashflowItem>;
}
export interface HkCashflow {
  code: string; name: string; market: string;
  currency: string | null; item_order: string[]; periods: HkCashflowPeriod[];
}

export const api = {
  authMe: () => get<AuthUser>("/auth/me"),
  register: (username: string, password: string, phone: string) => request<AuthUser>("/auth/register", "POST", { username, password, phone }),
  login: (username: string, password: string) => request<AuthUser>("/auth/login", "POST", { username, password }),
  logout: () => request<void>("/auth/logout", "POST"),
  aiCredential: () => get<AiCredentialStatus>("/ai/credential"),
  saveAiCredential: (apiKey: string, baseUrl: string, model: string) => request<AiCredentialStatus>("/ai/credential", "PUT", { api_key: apiKey, base_url: baseUrl, model }),
  deleteAiCredential: () => request<void>("/ai/credential", "DELETE"),
  watchlist: () => get<WatchlistItem[]>("/watchlist"),
  addWatchlist: (code: string) => request<WatchlistItem>("/watchlist", "POST", { code }),
  deleteWatchlist: (id: string) => request<void>(`/watchlist/${encodeURIComponent(id)}`, "DELETE"),
  health: () => get<{ ok: boolean }>("/health"),
  indices: () => get<IndexQuote[]>("/indices"),
  indexCandles: (symbols: string[], limit = 1) =>
    get<IndexSeries[]>(`/market/index-candles?symbols=${encodeURIComponent(symbols.join(","))}&period=1d&limit=${limit}`),
  marketOverview: () => get<MarketOverview>("/market/overview"),
  emotion: () => get<ShortTermEmotion>("/market/emotion"),
  turnoverTop: () => get<TurnoverTop>("/market/turnover-top"),
  globalIndices: () => get<GlobalIndex[]>("/global/indices"),
  globalStock: (symbol: string) => get<GlobalStock>(`/global/stock?symbol=${encodeURIComponent(symbol)}`),
  hkCashflow: (symbol: string) => get<HkCashflow>(`/global/hk/cashflow?symbol=${encodeURIComponent(symbol)}`),
  radar: () => get<RadarData>("/radar"),
  radarRefresh: () => request<RadarData>("/radar/refresh", "POST"),
  portfolio: () => get<PortfolioData>("/portfolio"),
  addHolding: (code: string, shares: number, cost: number) => request<Holding>("/portfolio/holding", "POST", { code, shares, cost }),
  removeHolding: (id: string) => request<void>(`/portfolio/holding/${encodeURIComponent(id)}`, "DELETE"),
  closePosition: (code: string, date: string, price: number, shares: number, cost: number) =>
    request<ClosedPosition>("/portfolio/close", "POST", { code, date, price, shares, cost }),
  removeClosed: (id: string) => request<void>(`/portfolio/close/${encodeURIComponent(id)}`, "DELETE"),
  notes: () => get<ResearchNote[]>("/notes"),
  addNote: (kind: string, title: string, content: string) => request<ResearchNote>("/notes", "POST", { kind, title, content }),
  deleteNote: (id: string) => request<void>(`/notes/${encodeURIComponent(id)}`, "DELETE"),
  valuation: (code: string) => get<Valuation>(`/valuation?code=${code}`),
  percentile: (code: string) => get<ValPercentile>(`/valuation/percentile?code=${code}`),
  financials: (code: string) => get<Financials>(`/financials?code=${code}`),
  announcements: (code: string) => get<Announcement[]>(`/announcements?code=${code}`),
  quote: (codes: string) => get<Record<string, Quote>>(`/quote?codes=${codes}`),
  reports: (code: string) => get<Report[]>(`/reports?code=${code}`),
  news: (code: string) => get<NewsItem[]>(`/news?code=${code}`),
  margin: (code: string) => get<MarginRow[]>(`/margin?code=${code}`),
  blockTrade: (code: string) => get<BlockTradeRow[]>(`/block-trade?code=${code}`),
  holders: (code: string) => get<HolderRow[]>(`/holders?code=${code}`),
  dividend: (code: string) => get<DividendRow[]>(`/dividend?code=${code}`),
  fundFlow: (code: string) => get<FundFlowRow[]>(`/fund-flow?code=${code}`),
  dragonTiger: (code: string) => get<DragonTiger>(`/dragon-tiger?code=${code}`),
  lockup: (code: string) => get<Lockup>(`/lockup?code=${code}`),
  blocks: (code: string) => get<Blocks>(`/blocks?code=${code}`),
  hotConcepts: (code: string) => get<HotConcept[]>(`/hot-concepts?code=${code}`),
  investorQa: (code: string) => get<QaRow[]>(`/investor-qa?code=${code}`),
  industry: (top = 20) => get<IndustryData>(`/industry?top=${top}`),
  allSectors: () => get<AllSectorsData>("/all-sectors"),
  sectorDetail: (kind: string, code: string) => get<SectorBoard>(`/sector-detail?kind=${encodeURIComponent(kind)}&code=${encodeURIComponent(code)}`),
  sectorMembers: (kind: string, code: string) => get<SectorMembers>(`/sector-members?kind=${encodeURIComponent(kind)}&code=${encodeURIComponent(code)}`),
  sectorRefreshStatus: () => get<SectorRefreshStatus>("/sectors/status"),
  sectorRefresh: () => request<SectorRefreshStatus>("/sectors/refresh", "POST"),
  stockSearch: (query: string, limit = 10) => get<StockSearch>(`/stocks/search?query=${encodeURIComponent(query)}&limit=${limit}`),
  myReports: () => get<MyReport[]>("/myreports"),
  uploadReport: (name: string, contentB64: string) =>
    request<MyReport>("/myreports", "POST", { name, content_b64: contentB64 }),
  deleteReport: (id: string) => request<void>(`/myreports/${id}`, "DELETE"),
};
