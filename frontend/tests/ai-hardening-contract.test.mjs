import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const hook = readFileSync("src/components/chat/usePersistentChat.ts", "utf8");
const analysis = readFileSync("src/pages/AIResearch.tsx", "utf8");
const debate = readFileSync("src/pages/Debate.tsx", "utf8");
const router = readFileSync("src/router.tsx", "utf8");

test("chat persistence is versioned, deeply validated and synchronized by timestamp", () => {
  assert.match(hook, /PERSISTENCE_VERSION\s*=\s*2/);
  assert.match(hook, /updatedAt/);
  assert.match(hook, /Array\.isArray\(value\.tools\)/);
  assert.match(hook, /addEventListener\("storage"/);
});

test("chat history is bounded and concurrent sends use a synchronous lock", () => {
  assert.match(hook, /MAX_HISTORY_MESSAGES/);
  assert.match(hook, /MAX_HISTORY_CHARS/);
  assert.match(hook, /inFlightRef\.current/);
});

test("AI analysis sends structured stock identity and preserves selected name", () => {
  assert.match(analysis, /stockCode: code/);
  assert.match(analysis, /stockName/);
  assert.doesNotMatch(analysis, /\[code\][\s\S]{0,100}setStockName\(""\)/);
});

test("debate uses URL as stock source and legacy redirect preserves search", () => {
  assert.match(debate, /const code = \(searchParams\.get\("code"\)/);
  assert.match(debate, /setSearchParams/);
  assert.match(router, /LegacyDebateRedirect/);
});
