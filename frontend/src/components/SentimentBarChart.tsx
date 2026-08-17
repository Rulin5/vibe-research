import { Info } from "lucide-react";
import type { MarketSentiment, ShortTermEmotion } from "@/lib/api";

interface Props { sentiment: MarketSentiment; emotion: ShortTermEmotion | null }

const pct = (value: number, total: number) => total ? value / total * 100 : 0;
const formatPct = (value: number) => `${value.toFixed(2)}%`;

function CardTitle({ children, hint }: { children: string; hint: string }) {
  return <div className="mb-5 flex items-center gap-2">
    <h4 className="text-base font-bold tracking-tight">{children}</h4>
    <span title={hint} className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-muted-foreground/45 text-muted-foreground"><Info className="h-2.5 w-2.5" /></span>
  </div>;
}

export function SentimentBarChart({ sentiment, emotion }: Props) {
  const total = sentiment.up + sentiment.down + sentiment.flat;
  const upPct = pct(sentiment.up, total);
  const flatPct = pct(sentiment.flat, total);
  const downPct = pct(sentiment.down, total);
  const structure = [
    { label: "涨停", value: sentiment.zt_real, color: "bg-danger", note: "真实涨停（乐咕）" },
    { label: "上涨", value: sentiment.up, color: "bg-danger/80", note: "上涨家数" },
    { label: "平盘", value: sentiment.flat, color: "bg-slate-300", note: "平盘家数" },
    { label: "下跌", value: sentiment.down, color: "bg-success/80", note: "下跌家数" },
    { label: "跌停", value: sentiment.dt_real, color: "bg-success", note: "真实跌停" },
  ];
  const maxStructure = Math.max(...structure.map((row) => row.value), 1);
  const rates = [
    { label: "封板率", value: emotion?.seal_rate == null ? null : emotion.seal_rate * 100, color: "from-blue-400 to-blue-600" },
    { label: "炸板率", value: emotion?.break_rate == null ? null : emotion.break_rate * 100, color: "from-sky-300 to-sky-500" },
    { label: "晋级率", value: emotion?.promotion_rate == null ? null : emotion.promotion_rate * 100, color: "from-violet-400 to-violet-600" },
  ];

  return <div className="grid gap-4 lg:grid-cols-3">
    <section className="min-w-0 rounded-2xl border border-border/70 bg-background/65 p-5 shadow-[0_10px_26px_rgba(30,60,100,.07)]">
      <CardTitle hint="上涨、平盘、下跌家数占全部有统计证券的比例">市场总览</CardTitle>
      <div className="grid grid-cols-[1fr_9.5rem_1fr] items-center gap-3 py-3">
        <div className="text-center"><div className="text-xs text-muted-foreground"><span className="mr-1 text-danger">●</span>上涨</div><strong className="mt-1 block font-mono text-2xl text-danger">{sentiment.up.toLocaleString("zh-CN")}</strong><span className="text-xs text-muted-foreground">{formatPct(upPct)}</span></div>
        <div className="relative mx-auto h-36 w-36 rounded-full" style={{ background: `conic-gradient(hsl(var(--danger)) 0 ${upPct}%, #cbd5e1 ${upPct}% ${upPct + flatPct}%, hsl(var(--success)) ${upPct + flatPct}% 100%)` }}>
          <div className="absolute inset-[19px] flex flex-col items-center justify-center rounded-full bg-card shadow-inner"><span className="text-[11px] text-muted-foreground">总交易只数</span><strong className="font-mono text-2xl">{total.toLocaleString("zh-CN")}</strong><span className="text-xs text-muted-foreground">只</span></div>
        </div>
        <div className="text-center"><div className="text-xs text-muted-foreground"><span className="mr-1 text-success">●</span>下跌</div><strong className="mt-1 block font-mono text-2xl text-success">{sentiment.down.toLocaleString("zh-CN")}</strong><span className="text-xs text-muted-foreground">{formatPct(downPct)}</span></div>
      </div>
      <div className="mt-4 flex justify-center gap-5 text-[11px] text-muted-foreground"><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-danger" />上涨</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-slate-300" />平盘</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-success" />下跌</span></div>
      <p className="mt-4 text-center text-[11px] leading-5 text-muted-foreground">市场快照 {sentiment.date || "—"} · 平盘 {sentiment.flat.toLocaleString("zh-CN")} 只（{formatPct(flatPct)}）</p>
    </section>

    <section className="min-w-0 rounded-2xl border border-border/70 bg-background/65 p-5 shadow-[0_10px_26px_rgba(30,60,100,.07)]">
      <CardTitle hint="同一纵轴展示涨停、上涨、平盘、下跌及跌停家数">涨跌结构</CardTitle>
      <div className="mb-4 grid grid-cols-3 gap-2 text-xs"><div><span className="text-muted-foreground">上涨</span><strong className="ml-2 text-danger">{sentiment.up.toLocaleString("zh-CN")}</strong><p>{formatPct(upPct)}</p></div><div><span className="text-muted-foreground">平盘</span><strong className="ml-2">{sentiment.flat.toLocaleString("zh-CN")}</strong><p>{formatPct(flatPct)}</p></div><div><span className="text-muted-foreground">下跌</span><strong className="ml-2 text-success">{sentiment.down.toLocaleString("zh-CN")}</strong><p>{formatPct(downPct)}</p></div></div>
      <div className="flex h-48 items-end justify-around gap-3 border-b border-border/80 px-2 pb-1">
        {structure.map((row) => <div key={row.label} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1"><strong className="font-mono text-xs">{row.value.toLocaleString("zh-CN")}</strong><div title={`${row.note} ${row.value}`} className={`w-full max-w-10 rounded-t-md ${row.color}`} style={{ height: `${Math.max(row.value / maxStructure * 78, row.value ? 8 : 2)}%` }} /><span className="whitespace-nowrap text-[10px] text-muted-foreground">{row.label}</span></div>)}
      </div>
      <p className="mt-4 text-center text-[11px] text-muted-foreground">红色为上涨方向，绿色为下跌方向；数量使用同一尺度</p>
    </section>

    <section className="min-w-0 rounded-2xl border border-border/70 bg-background/65 p-5 shadow-[0_10px_26px_rgba(30,60,100,.07)]">
      <CardTitle hint="短线情绪采用封板、炸板、晋级三个真实比例，不虚构历史成交额">情绪活跃度</CardTitle>
      <div className="space-y-5 py-1">{rates.map((row) => <div key={row.label}><div className="mb-2 flex items-end justify-between"><span className="text-sm text-muted-foreground">{row.label}</span><strong className="font-mono text-xl">{row.value == null ? "—" : `${row.value.toFixed(1)}%`}</strong></div><div className="h-3 overflow-hidden rounded-full bg-muted/70"><div className={`h-full rounded-full bg-gradient-to-r ${row.color}`} style={{ width: `${Math.min(Math.max(row.value ?? 0, 0), 100)}%` }} /></div></div>)}</div>
      <div className="mt-6 grid grid-cols-3 divide-x divide-border rounded-xl bg-muted/35 py-4 text-center"><div><span className="text-[10px] text-muted-foreground">封板（东财）</span><strong className="block font-mono text-lg text-danger">{emotion?.zt_count ?? "—"}</strong></div><div><span className="text-[10px] text-muted-foreground">炸板（东财）</span><strong className="block font-mono text-lg text-warning">{emotion?.zb_count ?? "—"}</strong></div><div><span className="text-[10px] text-muted-foreground">最高连板</span><strong className="block font-mono text-lg text-primary">{emotion ? `${emotion.max_boards}板` : "—"}</strong></div></div>
      <p className="mt-4 text-center text-[11px] text-muted-foreground">数据日期 {emotion?.date || sentiment.date || "—"} · 客观统计，不构成投资建议</p>
    </section>
  </div>;
}
