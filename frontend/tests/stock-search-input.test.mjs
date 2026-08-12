import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const component = readFileSync(new URL("../src/components/StockSearchInput.tsx", import.meta.url), "utf8");
const pages = ["DailyReview", "Debate", "Portfolio", "StockData", "Watchlist"].map((name) => [name, readFileSync(new URL(`../src/pages/${name}.tsx`, import.meta.url), "utf8")]);

test("shared stock search resolves TeaJoin names and codes", () => {
  assert.match(component, /api\.stockSearch/);
  assert.match(component, /股票名称或代码/);
  assert.match(component, /stock\.name/);
  assert.match(component, /stock\.code/);
  assert.match(component, /onSelect\?\.\(stock\)/);
});

test("every stock-code entry uses the shared name search", () => {
  for (const [name, source] of pages) {
    assert.match(source, /StockSearchInput/, `${name} must use StockSearchInput`);
  }
  assert.ok((pages.find(([name]) => name === "Portfolio")[1].match(/<StockSearchInput/g) || []).length >= 2, "Portfolio must cover holding and close forms");
});

test("selected results keep a normalized six-digit code", () => {
  assert.match(component, /onChange\(stock\.code\)/);
  assert.match(component, /已选择/);
});
