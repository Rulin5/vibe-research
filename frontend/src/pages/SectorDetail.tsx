import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, BookmarkPlus, Hash, Lightbulb, Building2 } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { GlassCard } from "@/components/ui/GlassCard";
import { AskAiButton } from "@/components/ui/AskAiButton";
import { api } from "@/lib/api";
import type { SectorBoard, SectorMember } from "@/lib/api";
import { cn } from "@/lib/utils";

export function SectorDetail() {
  const { kind, code } = useParams<{ kind: string; code: string }>();
  const [sector, setSector] = useState<SectorBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [members, setMembers] = useState<SectorMember[]>([]);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [membersLoading, setMembersLoading] = useState(false);

  useEffect(() => {
    if (!kind || !code) return;
    setLoading(true);
    setMembersLoading(true);
    setMembers([]);
    setMembersError(null);
    api.sectorDetail(kind, decodeURIComponent(code))
      .then((d) => { setSector(d); setLoading(false); })
      .catch(() => setLoading(false));
    api.sectorMembers(kind, decodeURIComponent(code))
      .then((d) => { setMembers(d.members); setMembersError(null); })
      .catch(() => setMembersError("成分股数据暂不可用，请稍后重试。"))
      .finally(() => setMembersLoading(false));
  }, [kind, code]);

  if (loading) {
    return (
      <div className="py-20 text-center text-muted-foreground">
        <p>正在加载板块数据...</p>
      </div>
    );
  }

  if (!sector) {
    return (
      <div className="py-20 text-center text-muted-foreground">
        <p>未找到该板块。</p>
        <Link to="/sectors" className="mt-2 inline-block text-primary hover:underline">返回板块中心</Link>
      </div>
    );
  }

  const isIndustry = sector.kind === "行业";
  const Icon = isIndustry ? Building2 : Lightbulb;
  const changePct = sector.pct_change;
  const hasData = sector.data_status === "complete";

  const aiContext =
    `板块：${sector.name}\n` +
    `类型：${sector.kind}板块\n` +
    (changePct != null
      ? `日线交易日：${sector.as_of}\n收盘点位：${sector.close}\n日线涨跌幅：${changePct > 0 ? "+" : ""}${changePct}%\n成分公司：${sector.member_count} 家\n领涨股：${sector.lead_stock}\n`
      : "验证快照中不存在完整日线数据\n") +
    `请帮我分析这个板块的投资逻辑、产业链环节和潜在风险。`;

  return (
    <div>
      <Link
        to="/sectors"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> 板块中心
      </Link>

      <PageHeader
        title={sector.name}
        subtitle={`${sector.kind}板块 · 代码 ${sector.code} · 日线交易日 ${sector.as_of}${sector.snapshot_id ? ` · 快照 ${sector.snapshot_id}` : ""}`}
        actions={
          <AskAiButton
            context={aiContext}
            label="让 AI 研究这个板块"
            suggestions={[
              "分析这个板块的投资逻辑",
              "梳理产业链上下游环节",
              "这个板块有哪些风险和催化因素",
            ]}
          />
        }
      />

      <GlassCard className="mb-4">
        <div className="flex items-start gap-4">
          <div className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl",
            isIndustry ? "bg-primary/15 text-primary" : "bg-accent/15 text-accent"
          )}>
            <Icon className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold">{sector.name}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <span className={cn(
                "rounded-md px-2 py-0.5 text-xs",
                isIndustry ? "bg-primary/10 text-primary/80" : "bg-accent/10 text-accent/80"
              )}>
                {sector.kind}板块
              </span>
              <span className="flex items-center gap-1">
                <Hash className="h-3.5 w-3.5" /> {sector.code}
              </span>
            </div>
          </div>
        </div>

        {/* 行业日线数据 */}
        {changePct != null && (
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-lg bg-muted/30 p-3 text-center">
              <p className="text-xs text-muted-foreground">收盘点位</p>
              <p className="mt-0.5 font-mono text-lg font-bold">{sector.close.toFixed(2)}</p>
            </div>
            <div className="rounded-lg bg-muted/30 p-3 text-center">
              <p className="text-xs text-muted-foreground">日线涨跌幅</p>
              <p className={cn(
                "mt-0.5 font-mono text-lg font-bold",
                changePct > 0 && "text-danger",
                changePct < 0 && "text-success",
                changePct === 0 && "text-muted-foreground"
              )}>
                {changePct > 0 ? "+" : ""}{changePct.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg bg-muted/30 p-3 text-center">
              <p className="text-xs text-muted-foreground">成分公司</p>
              <p className="mt-0.5 font-mono text-lg font-bold">{sector.member_count}</p>
            </div>
            <div className="rounded-lg bg-muted/30 p-3 text-center">
              <p className="text-xs text-muted-foreground">领涨股</p>
              <p className="mt-0.5 truncate text-sm font-bold">{sector.lead_stock || "—"}</p>
            </div>
          </div>
        )}

        {/* 快照异常提示 */}
        {!hasData && (
          <div className="mt-4 rounded-lg bg-muted/20 p-3 text-xs text-muted-foreground">
            <p>该板块未通过日线与成分股完整性校验，因此不会作为可用板块展示。</p>
          </div>
        )}

        <div className="mt-5 border-t border-border/50 pt-4">
          <h3 className="text-sm font-semibold">板块成分股</h3>
          {membersError ? <p className="mt-2 text-xs text-muted-foreground">{membersError}</p> : membersLoading ? (
            <p className="mt-2 text-xs text-muted-foreground">正在加载真实成分股数据…</p>
          ) : (
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {members.map((member) => (
                <Link key={member.code} to={`/stock-data?code=${encodeURIComponent(member.code)}`} className="rounded-lg bg-muted/30 px-3 py-2 text-sm hover:bg-primary/10">
                  <b className="block truncate">{member.name}</b><span className="font-mono text-xs text-muted-foreground">{member.code}</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* 研究入口提示 */}
        <div className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground">
          <BookmarkPlus className="h-3.5 w-3.5" />
          <span>想把这个板块加入自选关注？在「自选股」页面批量添加相关标的代码。</span>
        </div>
      </GlassCard>


    </div>
  );
}
