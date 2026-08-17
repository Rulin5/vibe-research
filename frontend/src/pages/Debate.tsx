import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Swords, Play, Square, Save, CheckCircle2, Circle, AlertTriangle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PageHeader } from "@/components/ui/PageHeader";
import { GlassCard } from "@/components/ui/GlassCard";
import { debateStream, type DebateStage } from "@/lib/agents";
import { api, ApiError, type StockSearchResult } from "@/lib/api";
import { StockSearchInput } from "@/components/StockSearchInput";
import { AskAiButton } from "@/components/ui/AskAiButton";

interface StageBox {
  stage: DebateStage;
  label: string;
  content: string;
  done: boolean;
}

// 多方用品牌橙、空方用蓝灰、主持用中性——刻意不用红绿，
// 免得和 A 股「红涨绿跌」撞车被读成涨跌信号。
const STAGE_TONE: Record<DebateStage, string> = {
  bull: "border-primary/50 bg-primary/[0.06]",
  bull_rebut: "border-primary/30 bg-primary/[0.03]",
  bear: "border-sky-500/40 bg-sky-500/[0.06]",
  bear_rebut: "border-sky-500/25 bg-sky-500/[0.03]",
  referee: "border-border bg-background/40",
};

const DOSSIER_HINT = "多空双方拿到的是同一份接口实时拉取的数据，谁也不能靠编数字赢。";

export function Debate() {
  const [searchParams, setSearchParams] = useSearchParams();
  const code = (searchParams.get("code") || "").trim();
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [rounds, setRounds] = useState(1);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState<{ title: string; ok: boolean }[]>([]);
  const [missing, setMissing] = useState<string[]>([]);
  const [stages, setStages] = useState<StageBox[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (selectedStock && selectedStock.code !== code) setSelectedStock(null);
  }, [code, selectedStock]);

  const reset = () => {
    setStatus(""); setProgress([]); setMissing([]); setStages([]); setError(""); setSaved(false);
  };

  async function start() {
    const c = code.trim();
    if (!/^\d{6}$/.test(c)) { setError("请输入 6 位 A 股代码"); return; }
    reset();
    setRunning(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await debateStream(c, rounds, {
        onStatus: setStatus,
        onDossierProgress: (title, ok, loaded, total) => {
          setStatus(`正在拉取客观事实底稿… ${loaded}/${total}`);
          setProgress((p) => [...p, { title, ok }]);
        },
        onDossierReady: (_sections, miss) => { setMissing(miss); setStatus("底稿就绪，研究开始"); },
        onStageStart: (stage, label) =>
          setStages((s) => [...s, { stage, label, content: "", done: false }]),
        onDelta: (stage, text) =>
          setStages((s) => s.map((b) => (b.stage === stage && !b.done ? { ...b, content: b.content + text } : b))),
        onStageDone: (stage, _label, content) =>
          setStages((s) => s.map((b) => (b.stage === stage && !b.done ? { ...b, content, done: true } : b))),
        onError: (message, stage) => setError(stage ? `${stage}：${message}` : message),
      }, ctrl.signal);
      setStatus("研究完成");
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") setStatus("已中止");
      else setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
    setRunning(false);
  }

  async function save() {
    const body = stages.map((s) => `## ${s.label}\n\n${s.content}`).join("\n\n---\n\n");
    const stockLabel = selectedStock ? `${selectedStock.name} ${selectedStock.code}` : code.trim();
    try { await api.addNote("AI 对话", `多角色研究 · ${stockLabel}`, body); setSaved(true); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "保存研究记录失败"); }
  }

  const finished = stages.length > 0 && stages.every((s) => s.done);
  const aiContext = useMemo(() => {
    const stockIdentity = selectedStock
      ? `当前研究股票：${selectedStock.name}（${selectedStock.code}，${selectedStock.market}${selectedStock.industry ? `，${selectedStock.industry}` : ""}）。`
      : code
        ? `当前研究股票代码：${code}。股票名称尚未由搜索结果确认。`
        : "当前尚未选择研究股票。";
    const completedResearch = stages.filter((stage) => stage.done && stage.content.trim()).map((stage) => `## ${stage.label}\n${stage.content.trim()}`).join("\n\n");
    const researchContext = completedResearch
      ? `\n\n研究流程输出：\n${completedResearch.slice(0, 30000)}${completedResearch.length > 30000 ? "\n[输出过长，已截取前 30000 字]" : ""}`
      : "\n\n当前还没有已完成的研究流程输出。";
    return `${stockIdentity}请优先基于客观数据回答，明确区分事实、推断与风险，不得虚构行情或财务数据。${researchContext}`;
  }, [code, selectedStock, stages]);

  const changeCode = (nextCode: string) => {
    const next = new URLSearchParams(searchParams);
    if (nextCode.trim()) next.set("code", nextCode.trim());
    else next.delete("code");
    setSearchParams(next, { replace: true });
    if (selectedStock?.code !== nextCode) setSelectedStock(null);
  };

  const selectStock = (stock: StockSearchResult) => {
    setSelectedStock(stock);
    changeCode(stock.code);
  };

  return (
    <div>
      <PageHeader
        title="AI辩论"
        subtitle="围绕真实市场数据提问，或启动多角色研究流程交叉验证。"
        actions={<AskAiButton context={aiContext} label="问 AI" scopeKey={code || "general"} suggestions={code ? ["总结当前研究分歧", "这只股票的基本面怎么样", "主要风险有哪些"] : ["今天市场有哪些重要变化", "如何分析一家公司", "帮我建立研究框架"]} />}
      />

      <GlassCard>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">股票名称或代码</label>
            <StockSearchInput value={code} onChange={changeCode} onSelect={selectStock} disabled={running} className="w-56" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">研究深度</label>
            <select
              value={rounds}
              onChange={(e) => setRounds(Number(e.target.value))}
              disabled={running}
              className="rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary/60"
            >
              <option value={1}>一轮 · 各自陈述</option>
              <option value={2}>两轮 · 加交叉反驳</option>
            </select>
          </div>
          {running ? (
            <button onClick={stop}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-4 py-2 text-sm hover:text-destructive">
              <Square className="h-4 w-4" /> 中止
            </button>
          ) : (
            <button onClick={start}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary/90 px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary">
              <Play className="h-4 w-4" /> 开始研究
            </button>
          )}
          {finished && !running && (
            <button onClick={save} disabled={saved}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-4 py-2 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50">
              <Save className="h-4 w-4" /> {saved ? "已存入沉淀" : "存入沉淀"}
            </button>
          )}
        </div>

        {/* 开销提示：辩论比问答重得多，让用户在点下去之前就知道要花多久、调几次模型 */}
        {!running && !status && (
          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground/70">
            ⏱ {rounds === 2
              ? "两轮约 3 分钟 · 5 次模型调用 · 约 6 万字进上下文"
              : "一轮约 100 秒 · 3 次模型调用 · 约 3.5 万字进上下文"}
            （每个角色都会带上完整底稿）。其中拉底稿约 35 秒、走公开数据接口，不消耗 token。
            省额度可用「订阅接入」的本机 CLI，或选中档模型——数据已备齐，模型只做组织和表达。
          </p>
        )}

        {status && <p className="mt-3 text-xs text-muted-foreground">{status}</p>}
        {error && (
          <p className="mt-3 flex items-start gap-1.5 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {error}
          </p>
        )}

        {progress.length > 0 && (
          <div className="mt-4 border-t border-border/40 pt-3">
            <p className="mb-2 text-[11px] text-muted-foreground">{DOSSIER_HINT}</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {progress.map((p) => (
                <span key={p.title} className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                  {p.ok
                    ? <CheckCircle2 className="h-3 w-3 text-primary/70" />
                    : <Circle className="h-3 w-3 text-muted-foreground/40" />}
                  {p.title}
                </span>
              ))}
            </div>
            {missing.length > 0 && (
              <p className="mt-2 text-[11px] text-warning">
                未取到：{missing.join("、")}（双方立论时不得臆测这部分）
              </p>
            )}
          </div>
        )}
      </GlassCard>

      <div className="mt-4 space-y-4">
        {stages.map((s) => (
          <div key={s.stage} className={`rounded-xl border p-4 ${STAGE_TONE[s.stage]}`}>
            <div className="mb-2 flex items-center gap-2">
              <Swords className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold">{s.label}</span>
              {!s.done && <span className="animate-pulse text-[11px] text-muted-foreground">生成中…</span>}
            </div>
            <div className="prose prose-sm dark:prose-invert max-w-none text-foreground prose-table:text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.content || "…"}</ReactMarkdown>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}
