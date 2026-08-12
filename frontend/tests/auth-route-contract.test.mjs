import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const main = readFileSync("src/main.tsx", "utf8");
const router = readFileSync("src/router.tsx", "utf8");
const provider = readFileSync("src/components/auth/AuthProvider.tsx", "utf8");
const api = readFileSync("src/lib/api.ts", "utf8");
const settings = readFileSync("src/pages/Settings.tsx", "utf8");

test("auth provider obtains the authenticated user from the server session", () => {
  assert.match(provider, /api\.authMe\(\)/);
  assert.match(main, /<AuthProvider>/);
});

test("private routes are guarded and settings is no longer public", () => {
  assert.match(router, /path: "\/watch"[\s\S]*<RequireAuth>/);
  assert.match(router, /path: "\/settings"[\s\S]*<RequireAuth>/);
  assert.match(router, /path: "\/login"/);
  assert.match(router, /path: "\/register"/);
});

test("API requests use cookies and protect writes with the CSRF header", () => {
  assert.match(api, /credentials:\s*"include"/);
  assert.match(api, /X-CSRF-Token/);
});

test("AI settings keep the original API model selector and save only on explicit user action", () => {
  assert.match(settings, /apiModels/);
  assert.match(settings, /subscriptionModels/);
  assert.match(settings, /Terminal/);
  assert.match(settings, /PROVIDER_BASE/);
  assert.match(settings, /saveAiCredential/);
  assert.doesNotMatch(settings, /localStorage/);
});
