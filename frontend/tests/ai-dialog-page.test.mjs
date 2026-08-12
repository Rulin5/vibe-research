import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../src/pages/Debate.tsx", import.meta.url), "utf8");
const layout = readFileSync(new URL("../src/components/layout/Layout.tsx", import.meta.url), "utf8");

test("debate page is renamed to AI conversation and exposes Ask AI", () => {
  assert.match(page, /title="AI 对话"/);
  assert.match(page, /<AskAiButton/);
  assert.match(page, /label="问 AI"/);
  assert.match(layout, /label: "AI 对话"/);
});

test("the obsolete empty-state copy is removed", () => {
  assert.doesNotMatch(page, /输入一个代码开始/);
  assert.doesNotMatch(page, /产出的是「分歧点 \+ 验证清单」/);
});

test("visible workflow copy consistently uses research language", () => {
  assert.match(page, /研究深度/);
  assert.match(page, /开始研究/);
  assert.match(page, /研究开始/);
  assert.match(page, /研究完成/);
  assert.doesNotMatch(page, />辩论深度</);
  assert.doesNotMatch(page, />开始辩论</);
});

test("selected stock identity and generated research are included in Ask AI context", () => {
  assert.match(page, /type StockSearchResult/);
  assert.match(page, /onSelect=\{setSelectedStock\}/);
  assert.match(page, /selectedStock\.name/);
  assert.match(page, /selectedStock\.code/);
  assert.match(page, /研究流程输出/);
  assert.match(page, /stages\.filter\(\(stage\) => stage\.done && stage\.content\.trim\(\)\)/);
  assert.match(page, /context=\{aiContext\}/);
});
