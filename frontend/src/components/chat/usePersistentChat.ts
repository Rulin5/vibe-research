import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/chatProtocol";
import { chatStream, type ChatMsg } from "@/lib/llm";
import { storageGet, storageRemove, storageSet } from "@/lib/storage";

const MAX_PERSISTED_MSGS = 40;
const MAX_HISTORY_MESSAGES = 30;
const MAX_HISTORY_CHARS = 40_000;
const PERSISTENCE_VERSION = 2;

export interface ToolUse {
  callId: string;
  name: string;
  label: string;
  arg: string;
  status: "running" | "completed" | "failed";
}

export type StoredMsg = ChatMsg & {
  tools?: ToolUse[];
  partial?: boolean;
  status?: "streaming" | "complete" | "failed";
};

interface StoredConversation { version: number; updatedAt: number; messages: StoredMsg[] }

function validTool(tool: unknown): tool is ToolUse {
  if (!tool || typeof tool !== "object") return false;
  const value = tool as Record<string, unknown>;
  return typeof value.callId === "string" && typeof value.name === "string" && typeof value.label === "string" &&
    typeof value.arg === "string" && (value.status === "running" || value.status === "completed" || value.status === "failed");
}

function validMessage(message: unknown): message is StoredMsg {
  if (!message || typeof message !== "object") return false;
  const value = message as Record<string, unknown>;
  return typeof value.content === "string" && (value.role === "user" || value.role === "assistant") &&
    (value.tools === undefined || (Array.isArray(value.tools) && value.tools.every(validTool))) &&
    (value.status === undefined || value.status === "streaming" || value.status === "complete" || value.status === "failed");
}

function loadConversation(key: string): StoredConversation {
  const raw = storageGet(key);
  if (!raw) return { version: PERSISTENCE_VERSION, updatedAt: 0, messages: [] };
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) return { version: PERSISTENCE_VERSION, updatedAt: 0, messages: parsed.filter(validMessage) };
    if (!parsed || typeof parsed !== "object") throw new Error("invalid conversation");
    const value = parsed as Record<string, unknown>;
    if (value.version !== PERSISTENCE_VERSION || !Array.isArray(value.messages)) throw new Error("unsupported conversation version");
    return { version: PERSISTENCE_VERSION, updatedAt: typeof value.updatedAt === "number" ? value.updatedAt : 0, messages: value.messages.filter(validMessage) };
  } catch {
    return { version: PERSISTENCE_VERSION, updatedAt: 0, messages: [] };
  }
}

function completeTurns(msgs: StoredMsg[]): StoredMsg[] {
  const out: StoredMsg[] = [];
  for (const message of msgs) {
    if (message.partial) {
      if (out.length && out[out.length - 1].role === "user") out.pop();
      continue;
    }
    out.push(message);
  }
  return out;
}

function saveChat(key: string, msgs: StoredMsg[]): void {
  if (!msgs.length) {
    storageRemove(key);
    return;
  }
  const keep = completeTurns(msgs);
  if (!keep.length) {
    storageRemove(key);
    return;
  }
  storageSet(key, JSON.stringify({ version: PERSISTENCE_VERSION, updatedAt: Date.now(), messages: keep.slice(-MAX_PERSISTED_MSGS) }));
}

function buildModelHistory(msgs: StoredMsg[]): ChatMsg[] {
  const selected: ChatMsg[] = [];
  let chars = 0;
  for (const message of completeTurns(msgs).slice().reverse()) {
    if (message.status === "failed") continue;
    if (selected.length >= MAX_HISTORY_MESSAGES || chars + message.content.length > MAX_HISTORY_CHARS) break;
    selected.push({ role: message.role, content: message.content });
    chars += message.content.length;
  }
  return selected.reverse();
}

function toolArg(args: Record<string, unknown>): string {
  if (Array.isArray(args.codes)) return args.codes.join(",");
  return typeof args.code === "string" ? args.code : "";
}

interface PersistentChatOptions {
  storageKey: string;
  context: string;
  researchMode?: boolean;
  stockCode?: string;
  stockName?: string;
}

interface SendOptions {
  researchQuestionId?: string | null;
}

export function usePersistentChat({ storageKey, context, researchMode = false, stockCode, stockName }: PersistentChatOptions) {
  const initial = loadConversation(storageKey);
  const [chat, setChat] = useState<{ key: string; msgs: StoredMsg[] }>(
    () => ({ key: storageKey, msgs: initial.messages }),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inFlightRef = useRef(false);
  const updatedAtRef = useRef(initial.updatedAt);
  const chatKeyRef = useRef(storageKey);
  chatKeyRef.current = storageKey;

  const setMsgs = useCallback((updater: StoredMsg[] | ((previous: StoredMsg[]) => StoredMsg[])) => {
    setChat((current) => ({
      key: current.key,
      msgs: typeof updater === "function" ? updater(current.msgs) : updater,
    }));
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setError(null);
    const loaded = loadConversation(storageKey);
    updatedAtRef.current = loaded.updatedAt;
    setChat({ key: storageKey, msgs: loaded.messages });
  }, [storageKey]);

  useEffect(() => {
    if (chat.key !== storageKey) return;
    if (chat.msgs.some((message) => message.partial || message.status === "streaming")) return;
    saveChat(storageKey, chat.msgs);
    updatedAtRef.current = Date.now();
  }, [storageKey, chat]);

  useEffect(() => {
    const receive = (event: StorageEvent) => {
      if (event.key !== storageKey || inFlightRef.current) return;
      const remote = loadConversation(storageKey);
      if (remote.updatedAt <= updatedAtRef.current) return;
      updatedAtRef.current = remote.updatedAt;
      setChat({ key: storageKey, msgs: remote.messages });
    };
    window.addEventListener("storage", receive);
    return () => window.removeEventListener("storage", receive);
  }, [storageKey]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    inFlightRef.current = false;
    setLoading(false);
  }, []);

  const clear = useCallback(() => {
    abort();
    setError(null);
    setMsgs([]);
  }, [abort, setMsgs]);

  const send = useCallback(async (text: string, options: SendOptions = {}) => {
    const question = text.trim();
    if (!question || loading || inFlightRef.current) return;
    inFlightRef.current = true;

    setError(null);
    const history: ChatMsg[] = [
      ...buildModelHistory(chat.msgs),
      { role: "user", content: question },
    ];
    setMsgs((messages) => [
      ...messages,
      { role: "user", content: question },
      { role: "assistant", content: "", tools: [], partial: true, status: "streaming" },
    ]);
    setLoading(true);

    const patchLast = (update: (message: StoredMsg) => StoredMsg) => {
      setMsgs((messages) => messages.map((message, index) =>
        index === messages.length - 1 && message.role === "assistant" ? update(message) : message,
      ));
    };

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const startedKey = chatKeyRef.current;
    const alive = () => abortRef.current === controller && !controller.signal.aborted;

    try {
      await chatStream(history, context, {
        onToolStarted: (callId, tool, label, args) => {
          if (alive()) patchLast((message) => ({
            ...message,
            tools: [...(message.tools || []), { callId, name: tool, label, arg: toolArg(args), status: "running" }],
          }));
        },
        onToolCompleted: (callId) => alive() && patchLast((message) => ({ ...message, tools: (message.tools || []).map((tool) => tool.callId === callId ? { ...tool, status: "completed" } : tool) })),
        onToolFailed: (callId) => alive() && patchLast((message) => ({ ...message, tools: (message.tools || []).map((tool) => tool.callId === callId ? { ...tool, status: "failed" } : tool) })),
        onDelta: (delta) => {
          if (alive()) patchLast((message) => ({ ...message, content: message.content + delta }));
        },
      }, controller.signal, {
        researchMode,
        researchQuestionId: options.researchQuestionId ?? null,
        stockCode,
        stockName,
      });
      if (alive()) patchLast((message) => {
        const { partial: _drop, ...rest } = message;
        return { ...rest, status: "complete" };
      });
    } catch (caught) {
      const superseded = abortRef.current !== null && abortRef.current !== controller;
      if (!superseded && chatKeyRef.current === startedKey) {
        setMsgs((messages) => {
          const last = messages[messages.length - 1];
          if (!last || last.role !== "assistant") return messages;
          if (last.content) return messages.map((message, index) => index === messages.length - 1 ? { ...message, status: "failed", partial: true } : message);
          const dropUser = messages[messages.length - 2]?.role === "user";
          return messages.slice(0, dropUser ? -2 : -1);
        });
        if (!controller.signal.aborted) {
          setError(caught instanceof ApiError ? caught.message : "对话失败");
        }
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        inFlightRef.current = false;
        setLoading(false);
      }
    }
  }, [chat.msgs, context, loading, researchMode, setMsgs, stockCode, stockName]);

  return { messages: chat.msgs, loading, error, send, clear, abort };
}
