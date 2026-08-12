import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../src/pages/DailyReview.tsx", import.meta.url), "utf8");
const chart = readFileSync(new URL("../src/components/MarketKlineChart.tsx", import.meta.url), "utf8");
const sentiment = readFileSync(new URL("../src/components/SentimentBarChart.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/lib/api.ts", import.meta.url), "utf8");

test("daily review consumes real batched index candles", () => {
  assert.match(api, /indexCandles:/);
  assert.match(api, /\/market\/index-candles/);
  assert.match(page, /api\.indexCandles/);
  assert.doesNotMatch(page, /mockCandles|demoCandles|fakeCandles/);
});

test("kline component owns and disposes ECharts", () => {
  assert.match(chart, /echarts\.init/);
  assert.match(chart, /type:\s*["']candlestick["']/);
  assert.match(chart, /type:\s*["']bar["']/);
  assert.match(chart, /ResizeObserver/);
  assert.match(chart, /dispose\(\)/);
});

test("market sentiment is rendered as count and rate bars", () => {
  assert.match(page, /SentimentBarChart/);
  assert.match(sentiment, /lg:grid-cols-3/);
  assert.match(sentiment, /市场总览/);
  assert.match(sentiment, /涨跌结构/);
  assert.match(sentiment, /情绪活跃度/);
  assert.match(sentiment, /conic-gradient/);
  assert.match(sentiment, /上涨家数/);
  assert.match(sentiment, /下跌家数/);
  assert.match(sentiment, /封板率/);
  assert.match(sentiment, /晋级率/);
  assert.match(sentiment, /seal_rate \* 100/);
  assert.doesNotMatch(sentiment, /近7日成交额|23356|24321/);
});

test("A-share polling follows 30 second session refresh", () => {
  assert.match(page, /30_000/);
  assert.match(page, /document\.visibilityState/);
  assert.match(page, /aShareSessionState/);
});
