import { useState, useEffect, useMemo } from "react";
import {
  Search, X, Building2, Lightbulb,
} from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { GlassCard } from "@/components/ui/GlassCard";
import { api } from "@/lib/api";
import type { SectorBoard, StockSearchResult } from "@/lib/api";

type KindFilter = "all" | "行业" | "概念";

const hasDailyClose = (s: SectorBoard) => s.data_status === "complete";

export function Sectors() {
  const [sectors, setSectors] = useState<SectorBoard[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [completeness, setCompleteness] = useState<{ published: number; candidate: number } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.allSectors()
      .then((d) => {
        if (!cancelled) {
          const all = [...d.industries, ...d.concepts];
          setSectors(all);
          setAsOf(d.as_of);
          setSnapshotId(d.snapshot_id);
          setCompleteness({ published: d.completeness.published_count, candidate: d.completeness.candidate_count });
          setLoadError(null);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError("验证板块快照暂不可用，请先刷新数据后重试。");
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  const refreshSnapshot = () => {
    setRefreshing(true);
    api.sectorRefresh()
      .then(() => api.sectorRefreshStatus())
      .catch(() => undefined)
      .finally(() => setRefreshing(false));
  };

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) { setStockResults([]); return; }
    const timer = window.setTimeout(() => {
      api.stockSearch(q).then((data) => setStockResults(data.results)).catch(() => setStockResults([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sectors.filter((s) => {
      if (kind !== "all" && s.kind !== kind) return false;
      if (q && !s.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [sectors, query, kind]);

  const industryCount = sectors.filter((s) => s.kind === "行业").length;
  const conceptCount = sectors.filter((s) => s.kind === "概念").length;
  const withDataCount = sectors.filter(hasDailyClose).length;

  return (
    <div>
      <PageHeader
        title="板块中心"
        subtitle={`${sectors.length} 个已验证行业与概念板块 · 日线收盘数据${asOf ? ` · 交易日 ${asOf}` : ""} · 不含个股推荐`}
        actions={
          <div className="flex items-center gap-2">
            <button onClick={refreshSnapshot} disabled={refreshing} className="h-9 rounded-lg border border-border/60 px-2 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50">
              {refreshing ? "刷新中" : "刷新数据"}
            </button>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索板块..."
                className="h-9 w-48 rounded-lg border border-border/60 bg-background/60 pl-8 pr-8 text-sm placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>
        }
      />

      {/* 分类筛选 tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {[
          { key: "all" as KindFilter, label: "全部", count: sectors.length },
          { key: "行业" as KindFilter, label: "行业板块", count: industryCount },
          { key: "概念" as KindFilter, label: "概念板块", count: conceptCount },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setKind(tab.key)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              kind === tab.key
                ? "bg-primary/15 text-primary shadow-glow"
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
            )}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      {stockResults.length > 0 && (
        <GlassCard className="mb-4 p-3">
          <p className="mb-2 text-xs text-muted-foreground">证券搜索（TeaJoin/Tushare 主数据）</p>
          <div className="flex flex-wrap gap-2">
            {stockResults.map((stock) => (
              <Link key={stock.ts_code} to={`/stock-data?code=${encodeURIComponent(stock.code)}`} className="rounded-md bg-muted/50 px-2.5 py-1.5 text-xs hover:bg-primary/10">
                <b>{stock.name}</b> <span className="font-mono text-muted-foreground">{stock.code}</span>
              </Link>
            ))}
          </div>
        </GlassCard>
      )}

      {loading ? (
        <div className="py-16 text-center text-muted-foreground">
          <p>正在加载板块数据...</p>
        </div>
      ) : loadError ? (
        <div className="py-16 text-center text-muted-foreground">
          <p>{loadError}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">
          <p>未找到匹配「{query}」的板块</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {filtered.map((s) => {
            const isUp = s.pct_change > 0;
            const isDown = s.pct_change < 0;
            const isIndustry = s.kind === "行业";
            const changePct = s.pct_change;
            const hasData = hasDailyClose(s);

            return (
              <Link key={`${s.kind}-${s.code}`} to={`/sectors/${s.kind}/${encodeURIComponent(s.code)}`}>
                <GlassCard className="flex h-full flex-col transition-transform hover:-translate-y-0.5">
                  {/* 图标 + 标题行 */}
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[10px]",
                      isIndustry ? "bg-primary/10 text-primary" : "bg-accent/10 text-accent"
                    )}>
                      {isIndustry ? <Building2 className="h-3.5 w-3.5" /> : <Lightbulb className="h-3.5 w-3.5" />}
                    </span>
                    <h3 className="flex-1 truncate text-sm font-bold">{s.name}</h3>
                    {hasData ? (
                      <span className={cn(
                        "shrink-0 font-mono text-sm font-semibold",
                        isUp && "text-danger",
                        isDown && "text-success",
                        !isUp && !isDown && "text-muted-foreground"
                      )}>
                        {isUp ? "+" : ""}{changePct.toFixed(2)}%
                      </span>
                    ) : (
                      <span className="shrink-0 text-[10px] text-muted-foreground/60">成分股</span>
                    )}
                  </div>

                  {/* 底部数据 */}
                  <div className="mt-2.5 flex items-center justify-between text-[10px] text-muted-foreground">
                    <div className="flex items-center gap-3">
                      {hasData && <>
                        <span>成分 {s.member_count}</span>
                        {s.lead_stock && <span className="truncate">领涨 {s.lead_stock}</span>}
                      </>}
                      {!hasData && (
                        <span>点击研究此板块</span>
                      )}
                    </div>
                    <span className={cn(
                      "rounded px-1.5 py-0.5",
                      isIndustry ? "bg-primary/8 text-primary/70" : "bg-accent/8 text-accent/70"
                    )}>
                      {s.kind}
                    </span>
                  </div>
                </GlassCard>
              </Link>
            );
          })}
        </div>
      )}

      <p className="mt-4 text-center text-xs text-muted-foreground/60">
        日线收盘数据 · 行业 {industryCount} 个、概念 {conceptCount} 个 · 已校验 {completeness?.published ?? withDataCount}/{completeness?.candidate ?? withDataCount} 个候选板块{asOf ? ` · 交易日 ${asOf}` : ""}{snapshotId ? ` · 快照 ${snapshotId}` : ""}。
      </p>
    </div>
  );
}
