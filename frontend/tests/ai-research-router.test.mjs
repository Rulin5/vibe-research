import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const llm = readFileSync("src/lib/llm.ts", "utf8");
const hook = readFileSync("src/components/chat/usePersistentChat.ts", "utf8");
const page = readFileSync("src/pages/AIResearch.tsx", "utf8");
const askAi = readFileSync("src/components/ui/AskAiButton.tsx", "utf8");

test("chat transport serializes optional research metadata", () => {
  assert.match(llm, /researchMode\?: boolean/);
  assert.match(llm, /researchQuestionId\?: string \| null/);
  assert.match(llm, /research_mode/);
  assert.match(llm, /research_question_id/);
});

test("AI research free questions use research mode and shortcut clicks send stable ids", () => {
  assert.match(page, /researchMode: true/);
  assert.match(page, /chat\.send\(question\.label, \{ researchQuestionId: question\.id \}\)/);
  assert.match(page, /chat\.send\(text\)/);
  assert.doesNotMatch(page, /BASE_RESEARCH_POLICY|Incremental Evidence Scan|Revenue Driver \+ Earnings Bridge/);
});

test("shared hook forwards per-message ids while Ask AI remains a legacy caller", () => {
  assert.match(hook, /researchMode\?: boolean/);
  assert.match(hook, /researchQuestionId\?: string \| null/);
  assert.doesNotMatch(askAi, /researchMode|researchQuestionId|research_question_id/);
});
