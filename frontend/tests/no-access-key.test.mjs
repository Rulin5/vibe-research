import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const FILES = [
  "../src/lib/api.ts",
  "../src/lib/llm.ts",
  "../src/lib/ndjson.ts",
  "../src/pages/Settings.tsx",
];

test("客户端不再包含后端访问密钥或授权请求头", async () => {
  for (const file of FILES) {
    const source = await readFile(new URL(file, import.meta.url), "utf8");
    assert.doesNotMatch(source, /VR_API_KEY|authHeaders|loadAccessKey|saveAccessKey|Authorization/);
  }
});
