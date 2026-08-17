export type ToolLifecycleStatus = "running" | "completed" | "failed";
import { ApiError } from "./api.ts";
export { ApiError } from "./api.ts";

export interface ParsedChatState {
  content: string;
  trace: { tool: string; args: Record<string, unknown> }[];
  rounds: number;
  done: boolean;
  events: Record<string, unknown>[];
}

export function apiErrorFromResponse(body: unknown, status: number): ApiError {
    const payload = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const nested = payload.error && typeof payload.error === "object" ? payload.error as Record<string, unknown> : null;
    if (nested) {
      const code = typeof nested.code === "string" ? nested.code : "request_failed";
      const message = typeof nested.message === "string" ? nested.message : friendlyError(code, status);
      return new ApiError(message, status, code);
    }
    if (typeof payload.detail === "string") return new ApiError(payload.detail, status);
    return new ApiError(friendlyError("request_failed", status), status);
}

function friendlyError(code: string, status: number): string {
  const messages: Record<string, string> = {
    invalid_research_question_id: "研究问题无效",
    request_too_large: "本次对话内容过长，请缩短后重试",
    stream_incomplete: "回答流意外中断，请重试",
  };
  return messages[code] || `请求失败 HTTP ${status}`;
}

export function parseChatEventLines(lines: string[], requireDone = false): ParsedChatState {
  const state: ParsedChatState = { content: "", trace: [], rounds: 0, done: false, events: [] };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(line) as Record<string, unknown>;
    } catch {
      throw new ApiError("后端响应格式错误", 502, "stream_protocol_error");
    }
    const type = event.type;
    if (type === "delta") state.content += typeof event.text === "string" ? event.text : "";
    else if (type === "done") {
      state.done = true;
      state.trace = Array.isArray(event.trace) ? event.trace as ParsedChatState["trace"] : [];
      state.rounds = typeof event.rounds === "number" ? event.rounds : 0;
    } else if (type === "error") {
      throw new ApiError(typeof event.message === "string" ? event.message : "对话服务暂时不可用", 502,
        typeof event.code === "string" ? event.code : "chat_failed");
    } else if (type !== "tool_started" && type !== "tool_completed" && type !== "tool_failed") {
      throw new ApiError("收到未知响应事件", 502, "stream_protocol_error");
    }
    state.events.push(event);
  }
  if (requireDone && !state.done) throw new ApiError("回答流意外中断，请重试", 502, "stream_incomplete");
  return state;
}
