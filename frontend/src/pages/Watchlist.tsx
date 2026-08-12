import { useMemo, useState } from "react";
import { Plus, RefreshCw, Star, X } from "lucide-react";

import { AskAiButton } from "@/components/ui/AskAiButton";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { useWatchlist } from "@/hooks/useWatchlist";
import { useLiveQuotes } from "@/hooks/useLiveQuotes";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { StockSearchInput } from "@/components/StockSearchInput";

const color = (value: number | undefined) => value == null ? "text-muted-foreground" : value > 0 ? "text-danger" : value < 0 ? "text-success" : "text-muted-foreground";
const pct = (value: number | undefined) => value == null ? "—" : `${value > 0 ? "+" : ""}${value}%`;

export function Watchlist() {
  const { items, codes, loading, refresh } = useWatchlist();
  const [input, setInput] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { quotes, updatedAt, error, refresh: refreshQuotes } = useLiveQuotes(codes, false);

  const add = async () => {
    const candidates = [...new Set((input.match(/\d{6}/g) || []))];
    if (!candidates.length) { setHint("请输入至少一个 6 位股票代码"); return; }
    setSubmitting(true); setHint(null);
    try {
      const settled = await Promise.allSettled(candidates.map((code) => api.addWatchlist(code)));
      const failures = settled.filter((result) => result.status === "rejected").length;
      await refresh(); setInput("");
      setHint(failures ? `已保存 ${candidates.length - failures} 只，${failures} 只未保存` : `已保存 ${candidates.length} 只自选`);
    } catch (err) { setHint(err instanceof ApiError ? err.message : "保存自选失败"); }
    finally { setSubmitting(false); }
  };

  const context = useMemo(() => codes.map((code) => {
    const quote = quotes[code];
    return quote ? `${quote.name}(${code}) 现价${quote.price} ${pct(quote.change_pct)}` : `${code}（行情未返回）`;
  }).join("\n"), [codes, quotes]);

  return <div>
    <PageHeader title="自选股" subtitle="账户专属自选；登录后在任意设备同步。" actions={codes.length ? <AskAiButton context={context} label="问 AI" suggestions={["按行业分组", "比较估值", "梳理主要风险"]} /> : undefined} />
    <GlassCard className="mb-4">
      <label className="mb-1.5 block text-xs text-muted-foreground">搜索股票名称或代码，选中后添加。</label>
      <div className="flex gap-2"><StockSearchInput value={input} onChange={setInput} className="flex-1" /><button onClick={add} disabled={submitting} className="inline-flex h-9 items-center gap-1.5 self-start rounded-lg bg-primary/15 px-4 text-sm text-primary disabled:opacity-50"><Plus className="h-4 w-4" />{submitting ? "保存中…" : "添加"}</button></div>
      {hint && <p className="mt-2 text-xs text-muted-foreground">{hint}</p>}
    </GlassCard>
    <GlassCard glow>
      <div className="mb-2 flex items-center justify-between"><h3 className="flex items-center gap-1.5 font-semibold"><Star className="h-4 w-4 text-primary" />自选总览 <span className="text-xs font-normal text-muted-foreground">({items.length})</span></h3><button onClick={() => { void refresh(); refreshQuotes(); }} className="text-muted-foreground hover:text-primary" title="刷新"><RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} /></button></div>
      {updatedAt && <p className="mb-2 text-[11px] text-muted-foreground">行情更新：{new Date(updatedAt).toLocaleTimeString("zh-CN", { hour12: false })}</p>}
      {error && <p className="mb-2 text-xs text-warning">行情暂不可用：{error}</p>}
      {!items.length ? <p className="py-8 text-center text-sm text-muted-foreground">还没有自选股票。</p> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-border/50 text-left text-xs text-muted-foreground"><th className="px-2 py-2">名称</th><th className="px-2 py-2">代码</th><th className="px-2 py-2">现价</th><th className="px-2 py-2">涨跌%</th><th /></tr></thead><tbody>{items.map((item) => { const quote = quotes[item.code]; return <tr key={item.id} className="border-b border-border/30"><td className="px-2 py-2.5">{quote?.name || "—"}</td><td className="px-2 py-2.5 font-mono text-xs">{item.code}</td><td className={cn("px-2 py-2.5 font-mono", color(quote?.change_pct))}>{quote?.price ?? "—"}</td><td className={cn("px-2 py-2.5 font-mono", color(quote?.change_pct))}>{pct(quote?.change_pct)}</td><td className="px-2 py-2.5"><button onClick={async () => { await api.deleteWatchlist(item.id); await refresh(); }} className="text-muted-foreground hover:text-destructive" title="移除"><X className="h-3.5 w-3.5" /></button></td></tr>; })}</tbody></table></div>}
    </GlassCard>
  </div>;
}
