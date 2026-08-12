import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const api = await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const sectors = await readFile(new URL("../src/pages/Sectors.tsx", import.meta.url), "utf8");
const detail = await readFile(new URL("../src/pages/SectorDetail.tsx", import.meta.url), "utf8");

test("client exposes real sector constituents and code/name stock search", () => {
  assert.match(api, /sectorMembers:/);
  assert.match(api, /\/sector-members\?/);
  assert.match(api, /stockSearch:/);
  assert.match(api, /\/stocks\/search\?/);
});

test("sector center renders stock-search matches", () => {
  assert.match(sectors, /api\.stockSearch/);
  assert.match(sectors, /stockResults/);
  assert.match(sectors, /\/stock-data\?code=/);
});

test("sector detail renders member stocks linked to the stock page", () => {
  assert.match(detail, /api\.sectorMembers/);
  assert.match(detail, /members/);
  assert.match(detail, /\/stock-data\?code=/);
  assert.match(detail, /membersLoading/);
  assert.match(detail, /membersError/);
});

test("sector UI does not label non-realtime TeaJoin classifications as live quotes", () => {
  assert.match(api, /close: number; pct_change: number; member_count: number/);
  assert.match(api, /data_status: "complete"/);
  assert.match(sectors, /s\.pct_change/);
  assert.match(sectors, /日线收盘数据/);
  assert.match(sectors, /TeaJoin\/Tushare/);
  assert.match(detail, /sector\.pct_change/);
  assert.match(detail, /日线交易日/);
});

test("sector UI consumes one verified snapshot and exposes refresh state", () => {
  assert.match(api, /snapshot_id: string/);
  assert.match(api, /data_status: "complete"/);
  assert.match(api, /sectorRefreshStatus:/);
  assert.match(api, /sectorRefresh:/);
  assert.match(sectors, /日线收盘数据/);
  assert.match(sectors, /snapshot_id/);
  assert.match(detail, /snapshot_id/);
});
