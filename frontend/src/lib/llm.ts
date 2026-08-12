import { ApiError } from "./api";

export interface ChatMsg { role: "user" | "assistant"; content: string; }
export interface ChatResult { content: string; trace: { tool: string; args: Record<string, unknown> }[]; rounds: number; }
export interface ChatHandlers { onDelta?: (text: string) => void; onTool?: (tool: string, args: Record<string, unknown>) => void; }

const STATUS_KEY = "vr-ai-configured";
const csrfToken = () => document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("vr_csrf="))?.slice("vr_csrf=".length) || "";

export function setLlmConfigured(configured: boolean) { if (configured) sessionStorage.setItem(STATUS_KEY, "1"); else sessionStorage.removeItem(STATUS_KEY); }
export function hasLlm() { return sessionStorage.getItem(STATUS_KEY) === "1"; }

export async function chatStream(messages: ChatMsg[], context: string, handlers: ChatHandlers = {}, signal?: AbortSignal): Promise<ChatResult> {
  let resp: Response;
  try { resp = await fetch("/api/chat", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() }, body: JSON.stringify({ messages, context }), signal }); }
  catch (cause) { if (cause instanceof DOMException && cause.name === "AbortError") throw cause; throw new ApiError("连接不到后端", 0); }
  if (!resp.ok) { let body: any = null; try { body = await resp.json(); } catch { /* no JSON */ } throw new ApiError(body?.detail || `HTTP ${resp.status}`, resp.status); }
  if (!resp.body) throw new ApiError("后端无响应流", 502);
  const reader = resp.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let content = ""; let trace: ChatResult["trace"] = []; let rounds = 0; let error: string | null = null;
  for (;;) {
    const { done, value } = await reader.read(); if (done) break;
    buffer += decoder.decode(value, { stream: true }); const lines = buffer.split("\n"); buffer = lines.pop() ?? "";
    for (const line of lines) { try { const event = JSON.parse(line); if (event.type === "delta") { content += event.text; handlers.onDelta?.(event.text); } else if (event.type === "tool") handlers.onTool?.(event.tool, event.args || {}); else if (event.type === "done") { trace = event.trace || []; rounds = event.rounds || 0; } else if (event.type === "error") error = event.message; } catch { /* ignore malformed NDJSON */ } }
  }
  if (error) throw new ApiError(error, 502); return { content, trace, rounds };
}
export const chat = (messages: ChatMsg[], context: string) => chatStream(messages, context);
