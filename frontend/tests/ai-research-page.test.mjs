import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const pagePath = "src/pages/AIResearch.tsx";
const questionsPath = "src/data/researchQuestions.ts";
const page = existsSync(pagePath) ? readFileSync(pagePath, "utf8") : "";
const questions = existsSync(questionsPath) ? readFileSync(questionsPath, "utf8") : "";
const router = readFileSync("src/router.tsx", "utf8");
const layout = readFileSync("src/components/layout/Layout.tsx", "utf8");
const askAi = readFileSync("src/components/ui/AskAiButton.tsx", "utf8");

test("AI research route and navigation sit between stock data and debate", () => {
  assert.match(router, /import \{ AIResearch \} from "@\/pages\/AIResearch"/);
  assert.match(router, /path: "analysis", element: <AIResearch \/>/);
  assert.match(router, /path: "debate", element: <Debate \/>/);
  assert.match(layout, /\/stock-data[\s\S]*\/ai-research\/analysis/);
  assert.match(layout, /label: "AI研究"/);
});

test("AI research defines twelve structured questions in two groups", () => {
  assert.ok(existsSync(questionsPath));
  for (const label of [
    "最近发生了什么？", "最新财报验证了什么？", "增长与利润弹性", "市场预期与预期差",
    "估值与定价框架", "公司怎么赚钱？", "近期异动归因", "盈利质量",
    "现金流与资本配置", "行业景气与周期", "竞争格局与价值捕获", "风险与证伪",
  ]) assert.match(questions, new RegExp(label.replace(/[？]/g, "\\？")));
  assert.equal((questions.match(/group: "primary"/g) || []).length, 6);
  assert.equal((questions.match(/group: "advanced"/g) || []).length, 6);
  assert.match(questions, /id: "growth_earnings"/);
});

test("AI research reuses streaming chat and supports optional stock context", () => {
  assert.ok(existsSync(pagePath));
  assert.match(page, /usePersistentChat/);
  assert.match(page, /ChatMessage/);
  assert.match(page, /useSearchParams/);
  assert.match(page, /searchParams\.get\("code"\)/);
  assert.match(page, /当前研究标的/);
  assert.match(page, /RESEARCH_QUESTIONS\.map/);
  assert.match(page, /question\.id/);
  assert.match(page, /chat\.send\(question\.label, \{ researchQuestionId: question\.id \}\)/);
  assert.match(page, /hasLlm\(\)/);
  assert.match(page, /to="\/settings"/);
});

test("Ask AI drawer and AI research share the conversation engine", () => {
  assert.match(askAi, /usePersistentChat/);
  assert.match(askAi, /ChatMessage/);
  assert.doesNotMatch(page, /fetch\(|\/api\/chat/);
});
