import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const readIfPresent = (path) => existsSync(path) ? readFileSync(path, "utf8") : "";

const dataPath = "src/data/assetAllocationScenarios.ts";
const pagePath = "src/pages/AssetAllocation.tsx";
const data = readIfPresent(dataPath);
const page = readIfPresent(pagePath);
const router = readFileSync("src/router.tsx", "utf8");
const layout = readFileSync("src/components/layout/Layout.tsx", "utf8");

test("asset allocation uses four fixed, conservative example scenarios", () => {
  assert.ok(existsSync(dataPath), "the local scenario data module must exist");
  for (const id of ["under-100k", "100k-to-500k", "500k-to-2m", "over-2m"]) {
    assert.match(data, new RegExp(`id: "${id}"`));
  }
  for (const id of ["liquidity", "fixed-income", "equity", "diversifier"]) {
    assert.match(data, new RegExp(`id: "${id}"`));
  }
  assert.match(data, /percentage: 70/);
  assert.match(data, /percentage: 40/);
});

test("asset allocation page is clearly educational and has no data or account linkage", () => {
  assert.ok(existsSync(pagePath), "the asset allocation page must exist");
  assert.match(page, /本页为静态教育性资产配置示例，不构成投资建议/);
  assert.match(page, /aria-pressed/);
  assert.match(page, /useState/);
  for (const forbidden of [/api\./, /fetch\(/, /useWatchlist/, /useAuth/, /chatStream/, /usePortfolio/]) {
    assert.doesNotMatch(page, forbidden);
  }
});

test("asset allocation is exposed as an independent application route and navigation item", () => {
  assert.match(router, /path: "\/asset-allocation"/);
  assert.match(layout, /to: "\/asset-allocation"/);
  assert.match(layout, /label: "资产配置"/);
});
