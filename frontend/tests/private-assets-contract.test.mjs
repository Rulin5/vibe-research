import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const api = readFileSync("src/lib/api.ts", "utf8");
const hook = readFileSync("src/hooks/useWatchlist.ts", "utf8");
const watchlist = readFileSync("src/pages/Watchlist.tsx", "utf8");
const dailyReview = readFileSync("src/pages/DailyReview.tsx", "utf8");
const intel = readFileSync("src/pages/Intel.tsx", "utf8");
const portfolio = readFileSync("src/pages/Portfolio.tsx", "utf8");
const notes = readFileSync("src/pages/Notes.tsx", "utf8");
const saveNoteButton = readFileSync("src/components/ui/SaveNoteButton.tsx", "utf8");

test("private watchlist client uses account APIs with immutable row IDs", () => {
  assert.match(api, /export interface WatchlistItem/);
  assert.match(api, /watchlist:\s*\(\)\s*=>\s*get<WatchlistItem\[\]>\("\/watchlist"\)/);
  assert.match(api, /addWatchlist:/);
  assert.match(api, /deleteWatchlist:/);
  assert.match(hook, /api\.watchlist\(\)/);
});

test("watchlist page does not use browser storage for security identities", () => {
  assert.match(watchlist, /useWatchlist\(\)/);
  assert.match(watchlist, /api\.addWatchlist/);
  assert.match(watchlist, /api\.deleteWatchlist/);
  assert.doesNotMatch(watchlist, /loadWatch|saveWatch|addCodes/);
});

test("public pages load account watch codes only after authentication", () => {
  assert.match(dailyReview, /useWatchlist\(\)/);
  assert.match(intel, /useWatchlist\(\)/);
  assert.doesNotMatch(dailyReview, /loadWatch|saveWatch/);
  assert.doesNotMatch(intel, /loadWatch/);
});

test("private assets use account-scoped row IDs rather than shared browser state", () => {
  assert.match(portfolio, /api\.portfolio\(\)/);
  assert.match(portfolio, /remove\(h\.id\)/);
  assert.match(portfolio, /removeClosed\(c\.id\)/);
  assert.match(notes, /api\.notes\(\)/);
  assert.match(notes, /api\.deleteNote/);
  assert.match(saveNoteButton, /api\.addNote/);
  assert.doesNotMatch(notes, /@\/lib\/notes/);
  assert.doesNotMatch(saveNoteButton, /@\/lib\/notes/);
});
