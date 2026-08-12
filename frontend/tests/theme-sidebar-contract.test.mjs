import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const themeHook = await readFile(new URL("../src/hooks/useDarkMode.ts", import.meta.url), "utf8");
const layout = await readFile(new URL("../src/components/layout/Layout.tsx", import.meta.url), "utf8");
const css = await readFile(new URL("../src/index.css", import.meta.url), "utf8");

test("theme defaults to light and migrates legacy dark preference to the soft gray theme", () => {
  assert.match(themeHook, /DEFAULT_THEME(?:\s*:\s*ThemeName)?\s*=\s*"light"/);
  assert.match(themeHook, /saved\s*===\s*"dark"[\s\S]*return\s+"soft"/);
  assert.match(themeHook, /"light", "soft", "deep"/);
});

test("sidebar contains a three-option theme selector without author or version footer content", () => {
  assert.match(layout, /THEME_OPTIONS\.map/);
  assert.match(layout, /亮色/);
  assert.match(layout, /浅灰/);
  assert.match(layout, /夜蓝/);
  assert.doesNotMatch(layout, /X_URL|MAIL_URL|APP_VERSION|Github|UserRound/);
});

test("soft is a light gray theme while deep remains a non-black night theme", () => {
  assert.match(css, /\.theme-soft\s*\{/);
  assert.match(css, /\.theme-deep\s*\{/);
  assert.match(css, /:root\s*\{[\s\S]*--background:\s*210\s+30%\s+97%/);
  assert.match(css, /\.theme-soft\s*\{[\s\S]*?--background:\s*215\s+14%\s+92%/);
  assert.match(themeHook, /const isDark = theme === "deep"/);
  assert.doesNotMatch(themeHook, /theme === "soft"\) root\.classList\.add\("dark"/);
});
