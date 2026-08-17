import { Check, Loader2, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { SaveNoteButton } from "@/components/ui/SaveNoteButton";
import type { StoredMsg } from "@/components/chat/usePersistentChat";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: StoredMsg;
  noteTitle?: string;
  noteKind?: string;
  streaming?: boolean;
}

export function ChatMessage({ message, noteTitle, noteKind = "问AI", streaming = false }: ChatMessageProps) {
  return (
    <div className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}>
      <div className={cn(
        "max-w-[88%] rounded-2xl px-4 py-3 leading-relaxed",
        message.role === "user" ? "bg-primary/20 text-foreground" : "bg-muted/40 text-foreground",
      )}>
        {message.tools && message.tools.length > 0 && (
          <div className="mb-2 flex flex-wrap items-center gap-1">
            <span className="text-[10px] text-muted-foreground/70">数据读取</span>
            {message.tools.map((tool, index) => (
              <span key={`${tool.name}-${index}`} className="inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary">
                {tool.status === "running" ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : tool.status === "completed" ? <Check className="h-2.5 w-2.5" /> : <X className="h-2.5 w-2.5" />}
                {tool.status === "running" ? "正在" : tool.status === "completed" ? "已" : "未能"}{tool.label || "读取数据"}{tool.arg ? ` ${tool.arg}` : ""}
              </span>
            ))}
          </div>
        )}
        {message.role === "assistant" ? (
          <div className="prose prose-sm dark:prose-invert max-w-none break-words text-foreground prose-table:block prose-table:max-w-full prose-table:overflow-x-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        ) : (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        )}
        {message.role === "assistant" && message.content && !streaming && noteTitle && (
          <div className="mt-2">
            <SaveNoteButton kind={noteKind} title={noteTitle} content={message.content} />
          </div>
        )}
      </div>
    </div>
  );
}
