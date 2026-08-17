import assert from "node:assert/strict";
import test from "node:test";

import { apiErrorFromResponse, parseChatEventLines } from "../src/lib/chatProtocol.ts";

test("normal delta and done completes the protocol", () => {
  const state = parseChatEventLines([
    '{"type":"delta","text":"hello"}',
    '{"type":"done","trace":[],"rounds":1}',
  ]);
  assert.equal(state.content, "hello");
  assert.equal(state.done, true);
});

test("delta followed by EOF without done is rejected", () => {
  assert.throws(() => parseChatEventLines(['{"type":"delta","text":"half"}'], true), /回答流意外中断/);
});

test("malformed NDJSON is rejected", () => {
  assert.throws(() => parseChatEventLines(["not-json"]), /响应格式错误/);
});

test("unknown stream event is rejected", () => {
  assert.throws(() => parseChatEventLines(['{"type":"mystery"}']), /未知响应事件/);
});

test("structured backend errors have friendly messages", () => {
  const error = apiErrorFromResponse({ error: { code: "invalid_research_question_id", message: "研究问题无效" } }, 400);
  assert.equal(error.message, "研究问题无效");
  assert.equal(error.code, "invalid_research_question_id");
});
