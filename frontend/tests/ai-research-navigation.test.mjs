import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const router = readFileSync("src/router.tsx", "utf8");
const layout = readFileSync("src/components/layout/Layout.tsx", "utf8");
const analysis = readFileSync("src/pages/AIResearch.tsx", "utf8");
const debate = readFileSync("src/pages/Debate.tsx", "utf8");
const shellPath = "src/pages/AIResearchLayout.tsx";
const shell = existsSync(shellPath) ? readFileSync(shellPath, "utf8") : "";

test("AI research is a parent route with analysis and debate children", () => {
  assert.match(router, /path: "\/ai-research"[\s\S]*<AIResearchLayout \/>/);
  assert.match(router, /path: "analysis", element: <AIResearch \/>/);
  assert.match(router, /path: "debate", element: <Debate \/>/);
  assert.match(router, /path: "\/debate"[\s\S]*LegacyDebateRedirect/);
});

test("the parent shell names and links both child pages", () => {
  assert.ok(existsSync(shellPath));
  assert.match(shell, /AI研究/);
  assert.match(shell, /to: "\/ai-research\/analysis", label: "AI分析"/);
  assert.match(shell, /to: "\/ai-research\/debate", label: "AI辩论"/);
  assert.match(shell, /<Outlet \/>/);
  assert.match(layout, /to: "\/ai-research\/analysis"[\s\S]*label: "AI研究"/);
  assert.doesNotMatch(layout, /label: "多空辩论"/);
});

test("AI analysis shows all twelve questions without a collapsed section", () => {
  assert.match(analysis, /title="AI分析"/);
  assert.match(analysis, /RESEARCH_QUESTIONS\.map/);
  assert.doesNotMatch(analysis, /showMore|更多研究|收起研究|ChevronDown|ChevronUp/);
});

test("AI debate receives the stock code preserved by the parent tabs", () => {
  assert.match(debate, /useSearchParams/);
  assert.match(debate, /searchParams\.get\("code"\)/);
});
