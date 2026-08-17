import { ApiError, apiErrorFromResponse, parseChatEventLines } from "./chatProtocol";

export interface ChatMsg { role: "user" | "assistant"; content: string; }
export interface ChatResult { content: string; trace: { tool: string; args: Record<string, unknown> }[]; rounds: number; }
export interface ChatHandlers {
  onDelta?: (text: string) => void;
  onToolStarted?: (callId: string, tool: string, label: string, args: Record<string, unknown>) => void;
  onToolCompleted?: (callId: string) => void;
  onToolFailed?: (callId: string) => void;
}
export interface ChatRequestOptions { researchMode?: boolean; researchQuestionId?: string | null; stockCode?: string; stockName?: string; }

const STATUS_KEY = "vr-ai-configured";
const csrfToken = () => document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("vr_csrf="))?.slice("vr_csrf=".length) || "";

export function setLlmConfigured(configured: boolean) { if (configured) sessionStorage.setItem(STATUS_KEY, "1"); else sessionStorage.removeItem(STATUS_KEY); }
export function hasLlm() { return sessionStorage.getItem(STATUS_KEY) === "1"; }

export async function chatStream(messages: ChatMsg[], context: string, handlers: ChatHandlers = {}, signal?: AbortSignal, options: ChatRequestOptions = {}): Promise<ChatResult> {
  let resp: Response;
  const body: Record<string, unknown> = { messages, context };
  if (options.researchMode) {
    body.research_mode = true;
    body.research_question_id = options.researchQuestionId ?? null;
  }
  if (options.stockCode) body.stock_code = options.stockCode;
  if (options.stockName) body.stock_name = options.stockName;
  try { resp = await fetch("/api/chat", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() }, body: JSON.stringify(body), signal }); }
  catch (cause) { if (cause instanceof DOMException && cause.name === "AbortError") throw cause; throw new ApiError("连接不到后端", 0); }
  if (!resp.ok) { let errorBody: unknown = null; try { errorBody = await resp.json(); } catch { /* no JSON */ } throw apiErrorFromResponse(errorBody, resp.status); }
  if (!resp.body) throw new ApiError("后端无响应流", 502);
  const reader = resp.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let content = ""; let trace: ChatResult["trace"] = []; let rounds = 0; let sawDone = false;
  const processLine = (line: string) => {
    const parsed = parseChatEventLines([line]);
    for (const event of parsed.events) {
      if (event.type === "delta") { const delta = String(event.text || ""); content += delta; handlers.onDelta?.(delta); }
      else if (event.type === "tool_started") handlers.onToolStarted?.(String(event.call_id || ""), String(event.tool_name || ""), String(event.label || "读取数据"), (event.args || {}) as Record<string, unknown>);
      else if (event.type === "tool_completed") handlers.onToolCompleted?.(String(event.call_id || ""));
      else if (event.type === "tool_failed") handlers.onToolFailed?.(String(event.call_id || ""));
      else if (event.type === "done") { sawDone = true; trace = Array.isArray(event.trace) ? event.trace as ChatResult["trace"] : []; rounds = Number(event.rounds || 0); }
    }
  };
  for (;;) {
    const { done, value } = await reader.read(); if (done) break;
    buffer += decoder.decode(value, { stream: true }); const lines = buffer.split("\n"); buffer = lines.pop() ?? "";
    for (const line of lines) processLine(line);
  }
  buffer += decoder.decode();
  if (buffer.trim()) processLine(buffer);
  if (!sawDone) throw new ApiError("回答流意外中断，请重试", 502, "stream_incomplete");
  return { content, trace, rounds };
}
export const chat = (messages: ChatMsg[], context: string) => chatStream(messages, context);
