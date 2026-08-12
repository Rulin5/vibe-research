import { useState, type CSSProperties } from "react";
import {
  BadgeCheck, CircleAlert, Droplets, Gem, Landmark, LineChart, Scale, ShieldCheck, WalletCards,
  type LucideIcon,
} from "lucide-react";

import {
  ASSET_ALLOCATION_SCENARIOS,
  formatExampleCny,
  type AllocationSlice,
} from "@/data/assetAllocationScenarios";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn } from "@/lib/utils";

const SLICE_ICONS: Record<AllocationSlice["id"], LucideIcon> = {
  liquidity: WalletCards,
  "fixed-income": ShieldCheck,
  equity: LineChart,
  diversifier: Gem,
};

const GUARDRAILS = [
  { icon: WalletCards, title: "先留出应急流动性", text: "先处理近期确定支出与 6–12 个月应急资金，再讨论长期配置。" },
  { icon: Scale, title: "先处理负债与保障缺口", text: "高成本负债和关键保障缺口，应优先于承担市场波动。" },
  { icon: ShieldCheck, title: "不使用杠杆，避免集中", text: "不把组合押注于单一证券、行业或短期市场判断。" },
];

function allocationGradient(allocation: AllocationSlice[]) {
  let start = 0;
  const stops = allocation.map((slice) => {
    const end = start + slice.percentage;
    const stop = `${slice.color} ${start}% ${end}%`;
    start = end;
    return stop;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

export function AssetAllocation() {
  const [selectedId, setSelectedId] = useState("500k-to-2m");
  const scenario = ASSET_ALLOCATION_SCENARIOS.find((item) => item.id === selectedId) ?? ASSET_ALLOCATION_SCENARIOS[2];
  const ringStyle = { background: allocationGradient(scenario.allocation) } as CSSProperties;

  return (
    <div className="pb-4">
      <PageHeader
        title="资产配置"
        subtitle="让不同时间要用的钱，待在合适的位置。"
        actions={<span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary"><Landmark className="h-3.5 w-3.5" />静态教育示例</span>}
      />

      <div className="mb-5 flex items-start gap-2 rounded-xl border border-primary/15 bg-primary/[0.06] px-4 py-3 text-xs leading-5 text-muted-foreground">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p>本页为静态教育性资产配置示例，不构成投资建议；请结合负债、现金流、期限、风险承受能力和适当性要求独立决策。</p>
      </div>

      <section className="mb-5" aria-label="资产规模区间">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">按金融资产规模查看保守示例</h2>
          <span className="text-xs text-muted-foreground">选择仅在当前页面生效</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {ASSET_ALLOCATION_SCENARIOS.map((item) => {
            const selected = item.id === selectedId;
            return (
              <button
                key={item.id}
                type="button"
                aria-pressed={selected}
                onClick={() => setSelectedId(item.id)}
                className={cn(
                  "rounded-xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
                  selected ? "border-primary/40 bg-primary/[0.08] shadow-glow" : "border-border bg-card/50 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-muted/35",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-foreground">{item.assetBandLabel}</span>
                  {selected && <BadgeCheck className="h-4 w-4 shrink-0 text-primary" aria-label="当前选择" />}
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">{item.stageLabel}</p>
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <GlassCard className="overflow-hidden p-0">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 px-5 py-4">
            <div>
              <p className="text-sm font-semibold">配置概览</p>
              <p className="mt-1 text-xs text-muted-foreground">{scenario.riskLabel} · 所有金额均为示例</p>
            </div>
            <div className="rounded-lg bg-muted/60 px-3 py-2 text-right">
              <p className="text-[11px] text-muted-foreground">示例金融资产总额</p>
              <p className="font-mono text-base font-bold text-foreground">{formatExampleCny(scenario.exampleTotal)}</p>
            </div>
          </div>
          <div className="grid items-center gap-6 p-5 sm:grid-cols-[180px_1fr]">
            <div className="relative mx-auto grid h-40 w-40 place-items-center rounded-full" style={ringStyle} aria-label="静态资产配置比例图">
              <div className="grid h-[112px] w-[112px] place-items-center rounded-full bg-background text-center shadow-sm">
                <span className="text-[11px] text-muted-foreground">保守配置</span>
                <strong className="text-xl tracking-tight">100%</strong>
              </div>
            </div>
            <div className="space-y-3">
              {scenario.allocation.map((slice) => (
                <div key={slice.id} className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: slice.color }} />
                  <span className="min-w-0 flex-1 text-sm text-foreground">{slice.label}</span>
                  <span className="font-mono text-sm font-semibold text-foreground">{slice.percentage}%</span>
                  <span className="w-24 text-right font-mono text-xs text-muted-foreground">{formatExampleCny(slice.exampleAmount)}</span>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-success" />
            <div><h2 className="text-sm font-semibold">保守配置的前提</h2><p className="mt-0.5 text-xs text-muted-foreground">先安排安全边界，再讨论配置比例。</p></div>
          </div>
          <div className="space-y-4">
            {GUARDRAILS.map(({ icon: Icon, title, text }) => (
              <div key={title} className="flex gap-3">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-success/10 text-success"><Icon className="h-4 w-4" /></span>
                <div><h3 className="text-sm font-medium">{title}</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">{text}</p></div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <section className="mt-5">
        <div className="mb-3"><h2 className="text-base font-bold">资金分桶示例</h2><p className="mt-1 text-xs text-muted-foreground">以 {formatExampleCny(scenario.exampleTotal)} 为静态示例，不对应你的真实资产。</p></div>
        <div className="grid gap-4 md:grid-cols-2">
          {scenario.allocation.map((slice) => {
            const Icon = SLICE_ICONS[slice.id];
            return (
              <GlassCard key={slice.id} className="group p-4 transition-transform hover:-translate-y-0.5">
                <div className="flex items-start gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ color: slice.color, backgroundColor: `${slice.color}18` }}><Icon className="h-5 w-5" /></span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">{slice.label}</h3><span className="font-mono text-base font-bold" style={{ color: slice.color }}>{slice.percentage}%</span></div>
                    <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{slice.description}</p>
                    <div className="mt-3 flex items-center justify-between border-t border-border/60 pt-3 text-xs"><span className="text-muted-foreground">示例金额</span><strong className="font-mono text-foreground">{formatExampleCny(slice.exampleAmount)}</strong></div>
                  </div>
                </div>
              </GlassCard>
            );
          })}
        </div>
      </section>

      <div className="mt-5 rounded-xl border border-border bg-muted/25 p-5">
        <div className="flex items-start gap-3"><Droplets className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><div><h2 className="text-sm font-semibold">使用边界</h2><p className="mt-1.5 text-xs leading-5 text-muted-foreground">本示例不识别你的收入、负债、家庭责任、税务、投资期限或风险承受能力，也不保证任何结果。若情况发生重要变化，可在年度回顾时重新审视资产分层；不要因短期市场波动频繁追涨杀跌。</p></div></div>
      </div>
    </div>
  );
}

export default AssetAllocation;
