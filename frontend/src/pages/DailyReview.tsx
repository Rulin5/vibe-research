import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Sparkles, Loader2, AlertCircle, RefreshCw, Gauge, ArrowDownUp, TrendingUp, TrendingDown, Plus, X, Flame, BarChart3, Globe } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PageHeader } from "@/components/ui/PageHeader";
import { GlassCard } from "@/components/ui/GlassCard";
import { AskAiButton } from "@/components/ui/AskAiButton";
import { api, ApiError, type IndexQuote, type Quote, type MarketOverview, type ShortTermEmotion, type TurnoverTop, type GlobalIndex, type IndexSeries } from "@/lib/api";
import { hasLlm, chatStream } from "@/lib/llm";
import { SaveNoteButton } from "@/components/ui/SaveNoteButton";
import { MarketKlineChart } from "@/components/MarketKlineChart";
import { SentimentBarChart } from "@/components/SentimentBarChart";
import { StockSearchInput } from "@/components/StockSearchInput";
import { useWatchlist } from "@/hooks/useWatchlist";
import { cn } from "@/lib/utils";

// A股红涨绿跌。全球市场（美股/港股指数）**也沿用红涨**——与整个看板及东财等中国平台一致，
// 对中国用户最不易看错（Simon 2026-07-05 确认；非国际绿涨惯例，是有意选择，勿改）。
const pctColor = (p: number) => (p > 0 ? "text-danger" : p < 0 ? "text-success" : "text-muted-foreground");
const fmt = (v: number) => v.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
const yi = (v: number | null) => (v == null ? "—" : `${fmt(v / 1e8)} 亿`); // 元 → 亿
const A_INDEX_SYMBOLS = ["CN.SH.000001", "CN.SZ.399001", "CN.SZ.399006", "CN.SH.000300"];
const GLOBAL_INDEX_SYMBOLS = ["GLOBAL.DJI", "GLOBAL.SPX", "GLOBAL.IXIC", "GLOBAL.HSI", "GLOBAL.HKTECH"];

function aShareSessionState(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }).formatToParts(now);
  const pick = (type: string) => parts.find((part) => part.type === type)?.value || "";
  if (["Sat", "Sun"].includes(pick("weekday"))) return "非交易日";
  const seconds = Number(pick("hour")) * 3600 + Number(pick("minute")) * 60 + Number(pick("second"));
  if (seconds < 9 * 3600 + 30 * 60) return "盘前";
  if (seconds <= 11 * 3600 + 30 * 60) return "盘中";
  if (seconds < 13 * 3600) return "午间休市";
  if (seconds <= 15 * 3600) return "盘中";
  return "已收盘";
}

function sameTradeDate(left: string | null | undefined, right: string | null | undefined) {
  const normalize = (value: string | null | undefined) => (value || "").match(/^\d{4}-\d{2}-\d{2}/)?.[0] || "";
  return Boolean(normalize(left) && normalize(left) === normalize(right));
}

export function DailyReview() {
  const [indices, setIndices] = useState<IndexQuote[]>([]);
  const [idxErr, setIdxErr] = useState(false);
  const [review, setReview] = useState("");
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewErr, setReviewErr] = useState<string | null>(null);
  const [needConfig, setNeedConfig] = useState(false);
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [emotion, setEmotion] = useState<ShortTermEmotion | null>(null);
  const [turnover, setTurnover] = useState<TurnoverTop | null>(null);
  const [globalIdx, setGlobalIdx] = useState<GlobalIndex[]>([]);
  const [indexSeries, setIndexSeries] = useState<IndexSeries[]>([]);
  const [selectedAIndex, setSelectedAIndex] = useState(A_INDEX_SYMBOLS[0]);
  const [selectedGlobalIndex, setSelectedGlobalIndex] = useState(GLOBAL_INDEX_SYMBOLS[1]);
  const [klineLoading, setKlineLoading] = useState(true);
  const [klineError, setKlineError] = useState<string | null>(null);
  const { items: watchItems, codes: watchCodes, refresh: refreshWatchlist } = useWatchlist();
  const [watchQuotes, setWatchQuotes] = useState<Record<string, Quote>>({});
  const [watchInput, setWatchInput] = useState("");
  const [watchSelection, setWatchSelection] = useState<{ name: string; code: string } | null>(null);
  const [watchLoading, setWatchLoading] = useState(false);

  // 各数据块请求是否已结束：区分「加载中」与「数据源暂不可用」（非交易时段/被限流时后端返回空）
  const [ovDone, setOvDone] = useState(false);
  const [emoDone, setEmoDone] = useState(false);
  const [toDone, setToDone] = useState(false);

  const loadIndices = () => {
    api.indices().then(setIndices).catch(() => setIdxErr(true));
    api.globalIndices().then(setGlobalIdx).catch(() => {});
    api.marketOverview().then(setOverview).catch(() => {}).finally(() => setOvDone(true));
    api.emotion().then(setEmotion).catch(() => {}).finally(() => setEmoDone(true));
    api.turnoverTop().then(setTurnover).catch(() => {}).finally(() => setToDone(true));
  };

  const loadIndexCandles = () => {
    setKlineLoading(true);
    api.indexCandles([...A_INDEX_SYMBOLS, ...GLOBAL_INDEX_SYMBOLS], 1)
      .then((rows) => { setIndexSeries(rows); setKlineError(null); })
      .catch((cause) => setKlineError(cause instanceof ApiError ? cause.message : "指数K线加载失败"))
      .finally(() => setKlineLoading(false));
  };

  // 数据块占位：请求没回来 = 加载中；回来了但为空 = 数据源暂不可用（别让用户干等）
  const pending = (done: boolean) => (
    <p className="py-4 text-center text-sm text-muted-foreground/60">
      {done ? "暂无数据：可能是非交易时段或数据源暂时不可用，可点「大盘指数」旁的刷新重试" : "加载中…"}
    </p>
  );

  const refreshWatch = (codes: string[]) => {
    if (!codes.length) { setWatchQuotes({}); return; }
    setWatchLoading(true);
    api.quote(codes.join(",")).then(setWatchQuotes).catch(() => {}).finally(() => setWatchLoading(false));
  };

  useEffect(() => { loadIndices(); loadIndexCandles(); }, []);

  useEffect(() => {
    const tick = () => {
      const hasOpenMarket = indexSeries.some((row) => row.market_session === "trading");
      const cnMarketClosedDay = indexSeries.filter((row) => row.market === "CN").every((row) => row.market_session === "closed_day");
      if (document.visibilityState === "visible" && (aShareSessionState() === "盘中" || hasOpenMarket) && (!cnMarketClosedDay || hasOpenMarket)) {
        loadIndices();
        loadIndexCandles();
      }
    };
    const timer = window.setInterval(tick, 30_000);
    const visible = () => { if (document.visibilityState === "visible") tick(); };
    document.addEventListener("visibilitychange", visible);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", visible); };
  }, [indexSeries]);

  useEffect(() => { refreshWatch(watchCodes); }, [watchCodes]);

  const addWatch = async () => {
    const codes = [...new Set(watchInput.match(/\d{6}/g) || [])];
    setWatchInput("");
    if (!codes.length) return;
    await Promise.allSettled(codes.map((code) => api.addWatchlist(code)));
    await refreshWatchlist();
    setWatchSelection(null);
  };

  const removeWatch = async (code: string) => {
    const item = watchItems.find((entry) => entry.code === code);
    if (!item) return;
    await api.deleteWatchlist(item.id);
    await refreshWatchlist();
  };

  const today = new Date().toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });

  const dataSummary = indices.length
    ? indices.map((i) => `${i.name} ${i.price}（${i.change_pct > 0 ? "+" : ""}${i.change_pct}%）`).join("；")
    : "（指数数据未取到）";

  const runReview = async () => {
    setReviewErr(null);
    setNeedConfig(false);
    if (!hasLlm()) { setNeedConfig(true); return; }
    setReviewLoading(true);
    setReview("");
    const prompt =
      `以下是今天 A 股大盘的客观数据：\n${dataSummary}\n\n` +
      "请用中文做一段当天大盘复盘：整体涨跌、主要指数表现、盘面值得注意的点。";
    try {
      await chatStream([{ role: "user", content: prompt }], `今日大盘数据：${dataSummary}`, {
        onDelta: (t) => setReview((r) => r + t),
      });
    } catch (e) {
      setReviewErr(e instanceof ApiError ? e.message : "复盘失败");
    } finally {
      setReviewLoading(false);
    }
  };

  const sentiment = overview?.sentiment;
  const sectors = overview?.sectors || [];
  const activeASeries = indexSeries.find((row) => row.symbol === selectedAIndex);
  const activeGlobalSeries = indexSeries.find((row) => row.symbol === selectedGlobalIndex);
  const alignedEmotion = sentiment && sameTradeDate(sentiment.date, emotion?.date) ? emotion : null;
  const sessionLabel = ({ pre_open: "盘前", trading: "盘中", lunch_break: "午间休市", closed: "已收盘", closed_day: "非交易日", local_market: "" } as const)[activeASeries?.market_session || "local_market"] || aShareSessionState();
  return (
    <div>
      <PageHeader
        title="每日复盘"
        subtitle={`${today} · 大盘 / 情绪 / 板块资金一屏看全，交给你的 AI 做复盘`}
        actions={
          <AskAiButton
            context={`今日大盘数据：${dataSummary}`}
            label="问 AI"
            suggestions={["今天大盘怎么走", "哪些指数领涨领跌", "盘面有什么值得注意"]}
          />
        }
      />

      {/* 1. 大盘指数：TeaJoin 真实日K */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2"><h3 className="text-sm font-semibold text-muted-foreground">大盘指数</h3><span className="text-[11px] text-muted-foreground/60">{sessionLabel}</span></div>
        <button onClick={() => { loadIndices(); loadIndexCandles(); }} className="text-muted-foreground hover:text-primary" title="刷新"><RefreshCw className={cn("h-3.5 w-3.5", klineLoading && "animate-spin")} /></button>
      </div>
      <GlassCard className="mb-6 overflow-hidden p-0">
        <div className="flex flex-wrap gap-2 border-b border-border/60 px-4 py-3">
          {indexSeries.filter((row) => row.market === "CN").map((row) => <button key={row.symbol} onClick={() => setSelectedAIndex(row.symbol)} className={cn("rounded-lg px-3 py-1.5 text-xs transition-colors", selectedAIndex === row.symbol ? "bg-primary/15 font-semibold text-primary" : "bg-muted/35 text-muted-foreground hover:text-foreground")}>{row.name}</button>)}
        </div>
        {activeASeries ? <><div className="flex flex-wrap items-baseline gap-3 px-5 pt-4"><strong className="text-base">{activeASeries.name}</strong><span className="text-xs text-muted-foreground">截至 {activeASeries.as_of} · {activeASeries.source}</span>{activeASeries.data_status === "source_unavailable" && <span className="rounded-full bg-warning/10 px-2 py-0.5 text-[11px] text-warning">TeaJoin 尚未提供该交易日 K 线</span>}</div><MarketKlineChart series={activeASeries} /></> : <p className="py-20 text-center text-sm text-muted-foreground">{klineError || (idxErr ? "行情未接通" : "K线加载中…")}</p>}
      </GlassCard>

      {/* 1b. 全球市场（隔夜外围脸色：A 股常看美股 / 港股） */}
      {(globalIdx.length > 0 || activeGlobalSeries) && (
        <>
          <div className="mb-3 flex items-center gap-2">
            <h3 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground"><Globe className="h-4 w-4" /> 全球市场</h3>
            <span className="text-[11px] text-muted-foreground/50">隔夜外围 · A 股常看美股 / 港股脸色</span>
          </div>
          <GlassCard className="mb-6 overflow-hidden p-0">
            <div className="flex flex-wrap gap-2 border-b border-border/60 px-4 py-3">{indexSeries.filter((row) => row.market !== "CN").map((row) => <button key={row.symbol} onClick={() => setSelectedGlobalIndex(row.symbol)} className={cn("rounded-lg px-3 py-1.5 text-xs transition-colors", selectedGlobalIndex === row.symbol ? "bg-primary/15 font-semibold text-primary" : "bg-muted/35 text-muted-foreground hover:text-foreground")}>{row.name}</button>)}</div>
            {activeGlobalSeries ? <><div className="flex flex-wrap items-baseline gap-3 px-5 pt-4"><strong className="text-base">{activeGlobalSeries.name}</strong><span className="text-xs text-muted-foreground">截至 {activeGlobalSeries.as_of} · {activeGlobalSeries.currency} · {activeGlobalSeries.timezone}</span>{activeGlobalSeries.data_status === "source_unavailable" && <span className="rounded-full bg-warning/10 px-2 py-0.5 text-[11px] text-warning">TeaJoin 尚未提供该交易日 K 线</span>}</div><MarketKlineChart series={activeGlobalSeries} height={300} /></> : <p className="py-16 text-center text-sm text-muted-foreground">K线加载中…</p>}
          </GlassCard>
        </>
      )}

      {/* 2. 关注股票（自选） */}
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-muted-foreground">关注股票</h3>
        {watchCodes.length > 0 && (
          <button onClick={() => refreshWatch(watchCodes)} className="text-muted-foreground hover:text-primary" title="刷新价格">
            {watchLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
      <GlassCard className="mb-6">
        <div className="mb-3 flex gap-2">
          <StockSearchInput value={watchInput} onChange={setWatchInput} onSelect={(stock) => setWatchSelection(stock)} className="w-72" placeholder="搜索股票名称或代码" />
          <button onClick={addWatch}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary/15 px-4 py-2 text-sm font-medium text-primary shadow-glow hover:bg-primary/25">
            <Plus className="h-4 w-4" /> 增加
          </button>
        </div>
        {watchSelection && <p className="mb-3 text-xs text-muted-foreground">待添加：<b className="text-foreground">{watchSelection.name}</b> <span className="font-mono">{watchSelection.code}</span></p>}
        {watchCodes.length === 0 ? (
          <p className="text-sm text-muted-foreground/60">加上你关注的股票，随时看它们的实时价格与涨跌。数据保存到当前账户。</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {watchCodes.map((c) => {
              const q = watchQuotes[c];
              return (
                <div key={c} className="group relative rounded-lg bg-muted/25 p-3">
                  <button onClick={() => removeWatch(c)} title="移除"
                    className="absolute right-1.5 top-1.5 text-muted-foreground/40 opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100">
                    <X className="h-3.5 w-3.5" />
                  </button>
                  <p className="truncate text-xs text-muted-foreground">{q?.name || c}</p>
                  <p className={cn("mt-1 font-mono text-lg font-bold", q ? pctColor(q.change_pct) : "text-muted-foreground/40")}>{q ? q.price : "—"}</p>
                  <p className={cn("text-xs", q ? pctColor(q.change_pct) : "text-muted-foreground/40")}>
                    {q ? `${q.change_pct > 0 ? "+" : ""}${q.change_pct}%` : c}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </GlassCard>

      {/* 3. AI 当日复盘 */}
      <GlassCard glow className="mb-6">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-1.5 font-semibold"><Sparkles className="h-4 w-4 text-primary" /> AI 当日复盘</h3>
          <button onClick={runReview} disabled={reviewLoading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary/15 px-4 py-2 text-sm font-medium text-primary shadow-glow hover:bg-primary/25 disabled:opacity-50">
            {reviewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {review ? "重新复盘" : "让 AI 复盘今天"}
          </button>
        </div>
        {needConfig && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4 shrink-0 text-warning" />
            还没接入 AI。<Link to="/settings" className="text-primary">先去接入你的 AI</Link>，之后一键出复盘。
          </div>
        )}
        {reviewErr && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" /> {reviewErr}
          </div>
        )}
        {review ? (
          <>
            <div className="prose prose-sm dark:prose-invert mt-4 max-w-none text-foreground"><ReactMarkdown remarkPlugins={[remarkGfm]}>{review}</ReactMarkdown></div>
            {!reviewLoading && <div className="mt-3"><SaveNoteButton kind="复盘" title={`每日复盘 ${today}`} content={review} /></div>}
          </>
        ) : !needConfig && !reviewErr && !reviewLoading ? (
          <p className="mt-3 text-sm text-muted-foreground">点上方按钮，系统把当天客观数据打包给你的 AI，由它生成复盘。<b className="text-foreground">分析是它给的，我们只负责喂数据。</b></p>
        ) : null}
      </GlassCard>

      {/* 4. 市场情绪 */}
      <div className="mb-3 flex items-center gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground"><Gauge className="h-4 w-4" /> 市场情绪</h3>
        {sentiment?.date && <span className="text-[11px] text-muted-foreground/50">{sentiment.date}</span>}
      </div>
      <GlassCard className="mb-6">
        {!sentiment?.breadth ? (
          pending(ovDone)
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { k: "大盘宽度", v: sentiment.breadth, hint: "冰点 / 偏弱 / 中性 / 偏强 / 普涨" },
                { k: "题材投机", v: sentiment.speculation, hint: "冰点 / 普通 / 活跃 / 亢奋" },
              ].map((m) => (
                <div key={m.k} className="rounded-lg bg-muted/25 p-4">
                  <p className="text-xs text-muted-foreground">{m.k}</p>
                  <p className="mt-1 text-2xl font-bold text-primary">{m.v}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground/60">{m.hint}</p>
                </div>
              ))}
            </div>
            <div className="mt-5"><SentimentBarChart sentiment={sentiment} emotion={alignedEmotion} /></div>
          </>
        )}
      </GlassCard>

      {/* 4b. 短线情绪（连板梯队 / 打板情绪，聚合口径零个股名） */}
      <div className="mb-3 flex items-center gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground"><Flame className="h-4 w-4" /> 短线情绪</h3>
        <span className="text-[11px] text-muted-foreground/50">连板股 · 打板情绪 · 客观公开榜单</span>
        {emotion?.date && <span className="ml-auto text-[11px] text-muted-foreground/50">{emotion.date}</span>}
      </div>
      <GlassCard className="mb-6">
        {!emotion || emotion.zt_count === undefined ? (
          pending(emoDone)
        ) : (
          <>
            {/* 关键计数 */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { k: "涨停", v: `${emotion.zt_count}`, cls: "text-danger" },
                { k: "跌停", v: `${emotion.dt_count}`, cls: "text-success" },
                { k: "最高连板", v: `${emotion.max_boards} 板`, cls: "text-primary" },
                { k: "连板（2板+）", v: `${emotion.lianban_count} 家`, cls: "text-primary" },
              ].map((c) => (
                <div key={c.k} className="rounded-lg bg-muted/25 p-3 text-center">
                  <p className="text-[11px] text-muted-foreground">{c.k}</p>
                  <p className={cn("mt-0.5 font-mono text-xl font-bold", c.cls)}>{c.v}</p>
                </div>
              ))}
            </div>
            {/* 打板情绪比率 */}
            <div className="mt-2 grid grid-cols-3 gap-2">
              {[
                { k: "封板率", v: emotion.seal_rate, hint: "封住 / 尝试涨停", strong: true },
                { k: "炸板率", v: emotion.break_rate, hint: "炸板 / 尝试涨停", strong: false },
                { k: "晋级率", v: emotion.promotion_rate, hint: "昨涨停今又停", strong: true },
              ].map((c) => (
                <div key={c.k} className="rounded-lg bg-muted/20 p-2.5 text-center">
                  <p className="text-[11px] text-muted-foreground">{c.k}</p>
                  <p className={cn("mt-0.5 font-mono text-sm font-bold", c.strong ? "text-danger" : "text-success")}>
                    {c.v == null ? "—" : `${(c.v * 100).toFixed(1)}%`}
                  </p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground/50">{c.hint}</p>
                </div>
              ))}
            </div>
            {/* 连板股清单（2 板以上，客观公开榜单） */}
            <div className="mt-3">
              <p className="mb-1.5 text-[11px] text-muted-foreground">连板股（2 板以上连续涨停）· 客观公开榜单，非推荐 / 非预测</p>
              {emotion.lianban_stocks.length === 0 ? (
                <p className="text-xs text-muted-foreground/50">今日无 2 板以上个股</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                        {["名称", "连板", "现价", "涨停%", "成交额", "流通市值", "概念"].map((h) => (
                          <th key={h} className="whitespace-nowrap px-2 py-2 font-medium">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {emotion.lianban_stocks.map((s) => (
                        <tr key={s.code} className="border-b border-border/30">
                          <td className="px-2 py-2"><span className="font-medium">{s.name}</span> <span className="text-xs text-muted-foreground/50">{s.code}</span></td>
                          <td className="whitespace-nowrap px-2 py-2 font-mono font-bold text-primary">{s.boards} 板</td>
                          <td className="px-2 py-2 font-mono">{s.price}</td>
                          <td className="px-2 py-2 font-mono text-danger">+{s.pct}%</td>
                          <td className="whitespace-nowrap px-2 py-2 font-mono text-muted-foreground">{yi(s.amount)}</td>
                          <td className="whitespace-nowrap px-2 py-2 font-mono text-muted-foreground">{yi(s.float_cap)}</td>
                          <td className="whitespace-nowrap px-2 py-2 text-xs text-muted-foreground">{s.industry}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </GlassCard>

      {/* 4c. 全市场成交额 TOP20（客观公开榜单） */}
      <div className="mb-3 flex items-center gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground"><BarChart3 className="h-4 w-4" /> 全市场成交额 TOP20</h3>
        {turnover?.updated && <span className="ml-auto text-[11px] text-muted-foreground/50">{turnover.updated}</span>}
      </div>
      <GlassCard className="mb-6">
        {!turnover || turnover.stocks.length === 0 ? (
          pending(toDone)
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                  {["#", "名称", "现价", "涨跌%", "成交额", "总市值", "行业"].map((h) => (
                    <th key={h} className="whitespace-nowrap px-2 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {turnover.stocks.map((s, i) => (
                  <tr key={s.code} className="border-b border-border/30">
                    <td className="px-2 py-2 font-mono text-xs text-muted-foreground/50">{i + 1}</td>
                    <td className="px-2 py-2"><span className="font-medium">{s.name}</span> <span className="text-xs text-muted-foreground/50">{s.code}</span></td>
                    <td className="px-2 py-2 font-mono">{s.price ?? "—"}</td>
                    <td className={cn("px-2 py-2 font-mono", s.pct == null ? "text-muted-foreground" : pctColor(s.pct))}>
                      {s.pct == null ? "—" : `${s.pct > 0 ? "+" : ""}${s.pct}%`}
                    </td>
                    <td className="whitespace-nowrap px-2 py-2 font-mono">{yi(s.amount)}</td>
                    <td className="whitespace-nowrap px-2 py-2 font-mono text-muted-foreground">{yi(s.mcap)}</td>
                    <td className="whitespace-nowrap px-2 py-2 text-xs text-muted-foreground">{s.industry}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>

      {/* 5. 板块资金趋势榜（行业） */}
      <div className="mb-3 flex items-center gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground"><TrendingUp className="h-4 w-4" /> 板块资金趋势榜</h3>
        <span className="text-[11px] text-muted-foreground/50">行业 · 按今日净流入排序</span>
      </div>
      <GlassCard className="mb-6">
        {sectors.length === 0 ? (
          pending(ovDone)
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                  {["行业", "涨跌%", "今日净流入", "流入", "流出", "家数"].map((h) => (
                    <th key={h} className="whitespace-nowrap px-2 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sectors.slice(0, 15).map((s) => (
                  <tr key={s.name} className="border-b border-border/30">
                    <td className="px-2 py-2 font-medium">{s.name}</td>
                    <td className={cn("px-2 py-2 font-mono", pctColor(s.pct))}>{s.pct > 0 ? "+" : ""}{s.pct}%</td>
                    <td className={cn("px-2 py-2 font-mono", pctColor(s.net))}>{s.net > 0 ? "+" : ""}{fmt(s.net)} 亿</td>
                    <td className="px-2 py-2 font-mono text-muted-foreground">{fmt(s.inflow)}</td>
                    <td className="px-2 py-2 font-mono text-muted-foreground">{fmt(s.outflow)}</td>
                    <td className="px-2 py-2 font-mono text-muted-foreground">{s.firms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>

      {/* 6. 资金轮动 */}
      <div className="mb-3 flex items-center gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground"><ArrowDownUp className="h-4 w-4" /> 资金轮动</h3>
        <span className="text-[11px] text-muted-foreground/50">板块级净流入 / 流出</span>
      </div>
      <div className="mb-2 grid gap-4 md:grid-cols-2">
        {[
          { title: "流入 Top", icon: TrendingUp, color: "text-danger", rows: sectors.slice(0, 6) },
          { title: "流出 Top", icon: TrendingDown, color: "text-success", rows: [...sectors].slice(-6).reverse() },
        ].map((col) => (
          <GlassCard key={col.title}>
            <h4 className={cn("mb-3 flex items-center gap-1.5 text-sm font-semibold", col.color)}><col.icon className="h-4 w-4" /> {col.title}</h4>
            {col.rows.length === 0 ? (
              pending(ovDone)
            ) : (
              <div className="space-y-1.5">
                {col.rows.map((s, i) => (
                  <div key={s.name} className="flex items-center gap-3 border-b border-border/30 pb-1.5 text-sm last:border-0">
                    <span className="w-5 text-xs text-muted-foreground/50">{i + 1}</span>
                    <span className="flex-1 truncate">{s.name}</span>
                    <span className={cn("font-mono text-xs", pctColor(s.pct))}>{s.pct > 0 ? "+" : ""}{s.pct}%</span>
                    <span className={cn("w-20 text-right font-mono text-xs", pctColor(s.net))}>{s.net > 0 ? "+" : ""}{fmt(s.net)} 亿</span>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        ))}
      </div>


    </div>
  );
}
