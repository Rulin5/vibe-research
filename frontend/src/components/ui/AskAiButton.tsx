import { useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2, Send, Settings, Sparkles, Trash2, X } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { ChatMessage } from "@/components/chat/ChatMessage";
import { usePersistentChat } from "@/components/chat/usePersistentChat";
import { hasLlm } from "@/lib/llm";

const CHAT_KEY_PREFIX = "vr-askai-chat:";

interface Props {
  context: string;
  suggestions?: string[];
  label?: string;
  scopeKey?: string;
}

export function AskAiButton({ context, suggestions = [], label = "问 AI", scopeKey }: Props) {
  const { pathname } = useLocation();
  const chatKey = CHAT_KEY_PREFIX + pathname + (scopeKey ? `#${scopeKey}` : "");
  const chat = usePersistentChat({ storageKey: chatKey, context });
  const [open, setOpen] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) setConfigured(hasLlm());
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chat.messages, chat.loading]);

  const close = () => {
    chat.abort();
    setOpen(false);
  };

  const send = (text: string) => {
    if (!text.trim()) return;
    setInput("");
    void chat.send(text);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-lg bg-primary/15 px-3 py-1.5 text-sm font-medium text-primary shadow-glow transition-colors hover:bg-primary/25"
      >
        <Sparkles className="h-4 w-4" />
        {label}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={close} />
          <aside className="glass relative m-3 flex w-full max-w-md flex-col rounded-2xl">
            <div className="flex items-center justify-between border-b border-border/60 p-4">
              <span className="flex items-center gap-2 font-semibold text-glow">
                <Sparkles className="h-4 w-4 text-primary" /> 问 AI · 本页上下文
              </span>
              <div className="flex items-center gap-1">
                {chat.messages.length > 0 && (
                  <button type="button" onClick={chat.clear} title="清空本页对话" aria-label="清空本页对话" className="text-muted-foreground hover:text-foreground">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
                <button type="button" onClick={close} className="text-muted-foreground hover:text-foreground" aria-label="关闭">
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {!configured ? (
              <div className="flex-1 space-y-4 overflow-auto p-4 text-sm">
                <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 text-xs text-muted-foreground">
                  请先接入AI。分析结论由你配置的 AI 给出，本产品只负责提供页面上下文和数据工具，不校准、不背书、不对结果负责。
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-muted-foreground">将随提问发送给 AI 的本页上下文：</p>
                  <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">{context}</pre>
                </div>
                <Link to="/settings" className="flex items-center justify-center gap-2 rounded-lg bg-primary/15 px-3 py-2 text-sm font-medium text-primary hover:bg-primary/25">
                  <Settings className="h-4 w-4" /> 先接入你的 AI（订阅 / API）
                </Link>
              </div>
            ) : (
              <>
                <div ref={scrollRef} className="flex-1 space-y-3 overflow-auto p-4 text-sm">
                  {chat.messages.length === 0 && (
                    <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 text-xs text-muted-foreground">
                      AI 可基于本页上下文，并自行调取 A股行情、估值、研报数据作答。结论由你的模型给出。
                    </div>
                  )}
                  {chat.messages.map((message, index) => (
                    <ChatMessage
                      key={index}
                      message={message}
                      streaming={chat.loading && index === chat.messages.length - 1}
                      noteKind="问AI"
                      noteTitle={`问 AI · ${chat.messages[index - 1]?.content?.slice(0, 24) || "对话"}`}
                    />
                  ))}
                  {chat.loading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> AI 正在思考 / 调取数据…
                    </div>
                  )}
                  {chat.error && (
                    <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {chat.error}
                    </div>
                  )}
                  {chat.messages.length === 0 && suggestions.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {suggestions.map((suggestion) => (
                        <button type="button" key={suggestion} onClick={() => send(suggestion)} className="rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs hover:border-primary/40 hover:text-primary">
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="border-t border-border/60 p-3">
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
                      rows={1}
                      placeholder="就本页内容提问…"
                      className="flex-1 resize-none rounded-lg border border-border bg-black/20 px-3 py-2 text-sm outline-none focus:border-primary/50"
                    />
                    <button type="button" onClick={() => send(input)} disabled={chat.loading || !input.trim()} className="rounded-lg bg-primary/15 p-2 text-primary hover:bg-primary/25 disabled:opacity-40" aria-label="发送">
                      <Send className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
