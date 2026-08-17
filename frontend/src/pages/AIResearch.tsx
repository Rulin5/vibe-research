import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Loader2, Send, Settings, Sparkles, Trash2 } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { ChatMessage } from "@/components/chat/ChatMessage";
import { usePersistentChat } from "@/components/chat/usePersistentChat";
import { StockSearchInput } from "@/components/StockSearchInput";
import { RESEARCH_QUESTIONS } from "@/data/researchQuestions";
import type { StockSearchResult } from "@/lib/api";
import { hasLlm } from "@/lib/llm";

const CHAT_KEY_PREFIX = "vr-ai-research-chat:";

export function AIResearch() {
  const [searchParams, setSearchParams] = useSearchParams();
  const code = (searchParams.get("code") || "").trim();
  const [stockQuery, setStockQuery] = useState(code);
  const [stockName, setStockName] = useState("");
  const selectedCodeRef = useRef("");
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const configured = hasLlm();

  useEffect(() => {
    setStockQuery(code);
    if (selectedCodeRef.current !== code) setStockName("");
  }, [code]);

  const context = useMemo(() => code
    ? `AI研究页面。当前研究标的：${stockName ? `${stockName} ` : ""}${code}。请基于用户问题作答；如需金融数据，使用现有可用工具。`
    : "AI研究页面。当前没有指定研究标的，用户可以提出一般金融研究问题；如需标的，请先向用户确认。",
  [code, stockName]);
  const chat = usePersistentChat({
    storageKey: `${CHAT_KEY_PREFIX}${code || "general"}`,
    context,
    researchMode: true,
    stockCode: code || undefined,
    stockName: stockName || undefined,
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chat.messages, chat.loading]);

  const selectStock = (stock: StockSearchResult) => {
    selectedCodeRef.current = stock.code;
    setStockName(stock.name);
    setSearchParams({ code: stock.code });
  };

  const send = (text: string) => {
    if (!configured || !text.trim()) return;
    setInput("");
    void chat.send(text);
  };

  return (
    <div className="flex min-h-[calc(100vh-9rem)] flex-col">
      <div className="mb-4">
        <h2 className="text-xl font-bold" title="AI分析">AI分析</h2>
        <p className="mt-1 text-sm text-muted-foreground">围绕真实金融问题持续对话，并使用Research Router加载对应研究规则。</p>
      </div>
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col overflow-hidden rounded-2xl border border-border/70 bg-card/55 shadow-sm">
        <div className="border-b border-border/60 px-5 py-4">
          <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
            <div>
              <p className="flex items-center gap-2 text-sm font-semibold">
                <Sparkles className="h-4 w-4 text-primary" /> 研究这个标的
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {code ? <>当前研究标的：<b className="text-foreground">{stockName ? `${stockName} ` : ""}{code}</b></> : "未指定标的，也可以直接提问。"}
              </p>
            </div>
            <StockSearchInput
              value={stockQuery}
              onChange={setStockQuery}
              onSelect={selectStock}
              placeholder="可选：输入股票名称或代码"
              className="w-full md:w-72"
            />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">
            {RESEARCH_QUESTIONS.map((question) => (
              <button
                type="button"
                key={question.id}
                data-question-id={question.id}
                disabled={!configured || chat.loading}
                onClick={() => chat.send(question.label, { researchQuestionId: question.id })}
                className="rounded-xl border border-border bg-background/60 px-3 py-2.5 text-left text-xs transition-colors hover:border-primary/45 hover:bg-primary/10 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {question.label}
              </button>
            ))}
          </div>
        </div>

        <div ref={scrollRef} className="min-h-[18rem] flex-1 space-y-4 overflow-auto px-5 py-5 md:px-10">
          {!configured ? (
            <div className="mx-auto mt-8 max-w-lg rounded-xl border border-warning/30 bg-warning/5 p-5 text-center">
              <Settings className="mx-auto h-6 w-6 text-primary" />
              <p className="mt-3 font-medium">请先接入AI</p>
              <p className="mt-1 text-sm text-muted-foreground">AI研究继续使用现有模型配置，不会创建第二套配置。</p>
              <Link to="/settings" className="mt-4 inline-flex rounded-lg bg-primary/15 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/25">
                前往接入 AI
              </Link>
            </div>
          ) : chat.messages.length === 0 ? (
            <div className="mx-auto mt-10 max-w-xl text-center text-sm text-muted-foreground">
              可以直接输入问题，或从上方选择一个研究方向。未选择股票时也可以自由聊天。
            </div>
          ) : (
            chat.messages.map((message, index) => (
              <ChatMessage
                key={index}
                message={message}
                streaming={chat.loading && index === chat.messages.length - 1}
                noteKind="AI研究"
                noteTitle={`AI研究 · ${chat.messages[index - 1]?.content?.slice(0, 24) || "对话"}`}
              />
            ))
          )}

          {chat.loading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> AI 正在思考 / 调取数据…
            </div>
          )}
          {chat.error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" /> {chat.error}
            </div>
          )}
        </div>

        <div className="border-t border-border/60 bg-card/80 px-5 py-4 md:px-10">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send(input);
                }
              }}
              rows={2}
              disabled={!configured}
              placeholder={configured ? "输入你的金融研究问题…" : "请先接入AI后开始研究"}
              className="min-h-12 flex-1 resize-none rounded-xl border border-border bg-background/70 px-4 py-3 text-sm outline-none focus:border-primary/55 disabled:cursor-not-allowed disabled:opacity-60"
            />
            <button
              type="button"
              onClick={() => send(input)}
              disabled={!configured || chat.loading || !input.trim()}
              className="rounded-xl bg-primary/15 p-3 text-primary hover:bg-primary/25 disabled:opacity-40"
              aria-label="发送"
            >
              <Send className="h-5 w-5" />
            </button>
            {chat.messages.length > 0 && (
              <button type="button" onClick={chat.clear} className="rounded-xl border border-border p-3 text-muted-foreground hover:text-foreground" aria-label="清空对话" title="清空对话">
                <Trash2 className="h-5 w-5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
