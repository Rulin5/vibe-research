import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../src/pages/DailyReview.tsx", import.meta.url), "utf8");
const chart = readFileSync(new URL("../src/components/MarketKlineChart.tsx", import.meta.url), "utf8");
const sentiment = readFileSync(new URL("../src/components/SentimentBarChart.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/lib/api.ts", import.meta.url), "utf8");

test("daily review consumes one current-trade-date TeaJoin K-line per selected index", () => {
  assert.match(api, /indexCandles:/);
  assert.match(api, /\/market\/index-candles/);
  assert.match(page, /api\.indexCandles/);
  assert.match(page, /api\.indexCandles\(\[\.\.\.A_INDEX_SYMBOLS, \.\.\.GLOBAL_INDEX_SYMBOLS\], 1\)/);
  assert.doesNotMatch(page, /mockCandles|demoCandles|fakeCandles|quote_at|realtime_available/);
});

test("K-line component owns and disposes ECharts without historic overlays", () => {
  assert.match(chart, /echarts\.init/);
  assert.match(chart, /type:\s*["']candlestick["']/);
  assert.match(chart, /ResizeObserver/);
  assert.match(chart, /dispose\(\)/);
  assert.doesNotMatch(chart, /MA20|movingAverage|dataZoom|type:\s*["']bar["']/);
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

test("daily review shows an explicit same-day source-unavailable state", () => {
  assert.match(page, /source_unavailable/);
  assert.match(page, /TeaJoin 尚未提供该交易日 K 线/);
});

test("market overview never mixes short-term emotion from a different trade date", () => {
  assert.match(page, /sameTradeDate/);
  assert.match(page, /alignedEmotion/);
  assert.match(page, /emotion=\{alignedEmotion\}/);
});

test("index series exposes source availability instead of calling stale data fresh", () => {
  assert.match(api, /"source_unavailable"/);
  assert.match(api, /status_reason/);
});

test("K-line volume leaves missing source data empty instead of plotting a zero", () => {
  assert.doesNotMatch(chart, /row\.volume \?\? 0/);
});

test("limit-up counts keep their source methodology visible", () => {
  assert.match(sentiment, /真实涨停（乐咕）/);
  assert.match(sentiment, /封板（东财）/);
});
