import { useEffect, useRef, useState } from "react";
import { Trash2, ChevronDown, ChevronRight, NotebookPen, ScanSearch, Save } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PageHeader } from "@/components/ui/PageHeader";
import { GlassCard } from "@/components/ui/GlassCard";
import { reflectStream } from "@/lib/agents";
import { api, ApiError, type ResearchNote } from "@/lib/api";

const KIND_COLOR: Record<string, string> = {
  "复盘": "bg-primary/15 text-primary",
  "今日要点": "bg-warning/15 text-warning",
  "问AI": "bg-success/15 text-success",
  "多空辩论": "bg-sky-500/15 text-sky-400",
  "AI 对话": "bg-primary/15 text-primary",
  "反思审计": "bg-violet-500/15 text-violet-400",
};

export function Notes() {
  const [notes, setNotes] = useState<ResearchNote[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reflectId, setReflectId] = useState<string | null>(null);
  const [reflectText, setReflectText] = useState("");
  const [reflectErr, setReflectErr] = useState("");
  const [reflecting, setReflecting] = useState(false);
  const [reflectSaved, setReflectSaved] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const load = async () => {
    try { setNotes(await api.notes()); setError(null); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "加载研究记录失败"); }
  };

  useEffect(() => { void load(); }, []);

  async function runReflect(note: ResearchNote) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setReflectId(note.id); setReflectText(""); setReflectErr(""); setReflectSaved(false); setReflecting(true);
    try {
      await reflectStream(note.content, note.title, {
        onDelta: (text) => setReflectText((current) => current + text),
        onError: setReflectErr,
      }, controller.signal);
    } catch (cause) {
      if (!(cause instanceof DOMException && cause.name === "AbortError")) {
        setReflectErr(cause instanceof ApiError ? cause.message : String(cause));
      }
    } finally {
      setReflecting(false);
    }
  }

  async function saveReflection(note: ResearchNote) {
    if (!reflectText.trim()) return;
    try {
      const saved = await api.addNote("反思审计", `反思 · ${note.title}`, reflectText);
      setNotes((current) => [saved, ...current]);
      setReflectSaved(true);
    } catch (cause) {
      setReflectErr(cause instanceof ApiError ? cause.message : "保存审计失败");
    }
  }

  async function remove(noteId: string) {
    try {
      await api.deleteNote(noteId);
      setNotes((current) => current.filter((note) => note.id !== noteId));
      if (openId === noteId) setOpenId(null);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "删除研究记录失败"); }
  }

  async function clearAll() {
    if (!confirm("清空所有研究记录？")) return;
    try {
      await Promise.all(notes.map((note) => api.deleteNote(note.id)));
      setNotes([]); setOpenId(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "清空失败，已刷新最新记录");
      await load();
    }
  }

  const fmt = (time: string) => new Date(time).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });

  return (
    <div>
      <PageHeader
        title="研究记录"
        subtitle="研究结果按账户隔离保存，登录后可在自己的设备间同步。"
        actions={notes.length > 0 && <button onClick={() => void clearAll()} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /> 清空</button>}
      />
      {error && <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
      {notes.length === 0 ? (
        <GlassCard><div className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground"><NotebookPen className="h-8 w-8 text-muted-foreground/40" />还没有记录。在复盘、资讯或问 AI 页面保存分析结果。</div></GlassCard>
      ) : <div className="space-y-2">{notes.map((note) => {
        const open = openId === note.id;
        return <GlassCard key={note.id} className="!p-0 overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3">
            <button onClick={() => setOpenId(open ? null : note.id)} className="flex flex-1 items-center gap-2 text-left">
              {open ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] ${KIND_COLOR[note.kind] || "bg-muted/50 text-muted-foreground"}`}>{note.kind}</span>
              <span className="flex-1 truncate text-sm font-medium">{note.title}</span><span className="shrink-0 font-mono text-[11px] text-muted-foreground/60">{fmt(note.updated_at)}</span>
            </button>
            <button onClick={() => void remove(note.id)} className="shrink-0 text-muted-foreground/60 hover:text-destructive" title="删除"><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
          {open && <div className="border-t border-border/40 px-4 py-3">
            <div className="prose prose-sm dark:prose-invert max-w-none text-foreground"><ReactMarkdown remarkPlugins={[remarkGfm]}>{note.content}</ReactMarkdown></div>
            <div className="mt-3 flex items-center gap-2 border-t border-border/40 pt-3"><button onClick={() => void runReflect(note)} disabled={reflecting} className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"><ScanSearch className="h-3.5 w-3.5" />{reflecting && reflectId === note.id ? "审计中…" : "反思审计"}</button></div>
            {reflectId === note.id && (reflectText || reflectErr) && <div className="mt-3 rounded-lg border border-violet-500/30 bg-violet-500/[0.05] p-3">{reflectErr ? <p className="text-xs text-destructive">{reflectErr}</p> : <><div className="prose prose-sm dark:prose-invert max-w-none text-foreground"><ReactMarkdown remarkPlugins={[remarkGfm]}>{reflectText}</ReactMarkdown></div>{!reflecting && <button onClick={() => void saveReflection(note)} disabled={reflectSaved} className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground disabled:opacity-50"><Save className="h-3 w-3" />{reflectSaved ? "已存为新记录" : "把审计结果存为新记录"}</button>}</>}</div>}
          </div>}
        </GlassCard>;
      })}</div>}
    </div>
  );
}
