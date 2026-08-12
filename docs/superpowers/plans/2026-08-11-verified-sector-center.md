# Verified Sector Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a sector center in which every displayed A-share industry or concept sector has one verified trading date, complete required day-data fields, and a non-empty validated constituent-stock list available on the detail page.

**Architecture:** Replace the current mixed live assembly (`moneyflow_ind_ths` for industries plus static `ths_index(type=N)` for concepts) with an immutable, date-keyed verified snapshot. A refresh worker obtains the same-trading-day industry and concept universes from TeaJoin, normalizes and validates every constituent list with `ths_member`, then atomically publishes the snapshot only when every public row is complete. Read APIs and detail pages read the same snapshot; they never make a new membership request that could produce an inconsistent or empty detail view.

**Tech Stack:** Python 3.12, FastAPI, TeaJoin/Tushare, standard-library JSON persistence and file locking, React 19, TypeScript, Vite, pytest, node:test.

## Global Constraints

- Market scope is mainland A-share sectors only; do not mix THS, Eastmoney, Sina, overseas, index, region, strategy, or historical classification universes in one list.
- A displayed sector must have: `ts_code`, Chinese name, `trade_date`, close, pct_change, company_num, lead_stock, net_amount, and at least one normalized constituent (`code`, `name`). Missing, invalid, or stale fields exclude the row from the public snapshot; never substitute zero, empty string, or another provider.
- The public response must include provider, market, timezone, trading date, retrieved time, snapshot id, method version, and completeness statistics. Upstream daily rows that cannot be mapped to any constituent are recorded as excluded diagnostics and never become public sectors.
- `moneyflow_ind_ths` and `moneyflow_cnt_ths` are daily close/fund-flow data, not intraday quotes. The UI must state the exact trading date and “日线收盘数据”.
- Data refresh is asynchronous, bounded, idempotent, and persisted under `VR_DATA_DIR`; normal `GET` requests must not synchronously validate hundreds of sectors.
- TeaJoin credentials remain only in ignored runtime configuration. No API key, raw token, or constituent data dump goes to logs.
- Existing `/api/all-sectors`, `/api/sector-detail`, `/api/sector-members`, and code/name stock search remain compatible; additions are backward-compatible fields and new refresh/status endpoints.

---

### Task 1: Define the verified snapshot contract and persistent store

**Files:**
- Create: `backend/sector_snapshot.py`
- Create: `backend/tests/test_sector_snapshot.py`
- Modify: `backend/conftest.py`

**Interfaces:**
- Consumes: `VR_DATA_DIR`, normalized provider records, and a clock.
- Produces: `SectorSnapshotStore.load_current() -> dict | None`, `SectorSnapshotStore.publish(snapshot: dict) -> None`, and `SectorSnapshotStore.load_members(snapshot_id: str, kind: str, code: str) -> list[dict]`.

- [ ] **Step 1: Write failing persistence and atomic-publication tests.**

```python
def test_store_only_exposes_a_completed_snapshot(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    store.save_refresh_state({"task_id": "t1", "status": "running"})
    assert store.load_current() is None
    store.publish({"snapshot_id": "20260811-v1", "status": "completed", "sectors": []})
    assert store.load_current()["snapshot_id"] == "20260811-v1"


def test_store_writes_snapshot_and_members_atomically(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    snapshot = {"snapshot_id": "20260811-v1", "status": "completed", "sectors": [{"kind": "行业", "code": "881101.TI"}]}
    store.publish(snapshot, {("行业", "881101.TI"): [{"code": "600000", "name": "浦发银行"}]})
    assert store.load_members("20260811-v1", "行业", "881101.TI")[0]["code"] == "600000"
```

- [ ] **Step 2: Run the new tests and confirm they fail because `sector_snapshot` does not exist.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_sector_snapshot.py -q`

Expected: import failure for `sector_snapshot`.

- [ ] **Step 3: Implement the store with atomic files and a process lock.**

```python
class SectorSnapshotStore:
    def __init__(self, root: Path):
        self.root = root / "sector-snapshots"

    def publish(self, snapshot: dict, members: dict[tuple[str, str], list[dict]]) -> None:
        # write `snapshot_id.json.tmp` and `snapshot_id-members.json.tmp`, fsync,
        # atomically replace both version files, then atomically replace current.json last
        ...
```

Store `current.json`, `refresh-state.json`, `<snapshot_id>.json`, and `<snapshot_id>-members.json` below `VR_DATA_DIR/sector-snapshots/`. `current.json` is written last and only references a fully written `status="completed"` snapshot. Preserve previous completed snapshots for rollback; do not delete them in this change.

- [ ] **Step 4: Re-run the store tests.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_sector_snapshot.py -q`

Expected: all tests pass.

### Task 2: Build and validate the same-day industry/concept universe

**Files:**
- Modify: `backend/astock.py`
- Create: `backend/tests/test_sector_universe.py`

**Interfaces:**
- Consumes: `teajoin.call("trade_cal")`, `teajoin.call("moneyflow_ind_ths")`, `teajoin.call("moneyflow_cnt_ths")`, and `teajoin.call("ths_member")`.
- Produces: `build_verified_sector_snapshot(trade_date: str | None = None) -> tuple[dict, dict[tuple[str, str], list[dict]]]`.

- [ ] **Step 1: Write failing contract tests for the canonical daily universe.**

```python
def test_snapshot_uses_same_day_industry_and_concept_daily_sources(monkeypatch):
    snapshot, members = astock.build_verified_sector_snapshot("20260811")
    assert {row["kind"] for row in snapshot["sectors"]} == {"行业", "概念"}
    assert {row["as_of"] for row in snapshot["sectors"]} == {"20260811"}
    assert all(row["source"] == "TeaJoin/Tushare" for row in snapshot["sectors"])
    assert all(row["close"] is not None and row["pct_change"] is not None for row in snapshot["sectors"])
    assert all(members[(row["kind"], row["code"])] for row in snapshot["sectors"])


def test_snapshot_rejects_daily_row_with_empty_or_incomplete_members(monkeypatch):
    snapshot, members = astock.build_verified_sector_snapshot("20260811")
    assert ("概念", "886112.TI") not in members
    assert "886112.TI" not in {row["code"] for row in snapshot["sectors"]}
```

- [ ] **Step 2: Run the universe tests and confirm they fail because the builder does not exist.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_sector_universe.py -q`

Expected: attribute error for `build_verified_sector_snapshot`.

- [ ] **Step 3: Implement one normalized source adapter per daily universe.**

```python
def _daily_industry_rows(trade_date: str) -> list[dict]:
    return teajoin.call("moneyflow_ind_ths", {"trade_date": trade_date}, _SECTOR_FIELDS)


def _daily_concept_rows(trade_date: str) -> list[dict]:
    return teajoin.call("moneyflow_cnt_ths", {"trade_date": trade_date}, _SECTOR_FIELDS)
```

Normalize both endpoint schemas into one record shape: `kind`, `code`, `name`, `as_of`, `close`, `pct_change`, `member_count`, `lead_stock`, `net_amount`, `source`, `market="CN-A"`, `currency="CNY"`, `timezone="Asia/Shanghai"`, `frequency="1d"`, and `retrieved_at`. Use endpoint names only as metadata; do not merge Eastmoney `moneyflow_ind_dc` rows because its codes cannot be resolved by `ths_member`.

- [ ] **Step 4: Validate membership before publication.**

For every daily candidate, call `ths_member(ts_code=code)` with the existing rate limiter, normalize six-digit A-share codes, reject blank names/codes and duplicate codes, and require one or more active constituents. Compare normalized active count with `company_num`; mark the candidate `rejected_member_count_mismatch` when the provider counts cannot be reconciled. Include rejected codes and reasons only in private refresh diagnostics, not in the public sector list.

- [ ] **Step 5: Make public completeness a hard publish gate.**

The snapshot metadata must record `candidate_count`, `published_count`, `excluded_count`, `excluded_by_reason`, and `provider_row_counts`, with the invariant `candidate_count == published_count + excluded_count`. An exclusion is allowed only before publication and only for a documented source-contract reason (such as no resolvable constituent); every published row must be complete. If either daily source is empty, every candidate in a public kind is excluded, the accounting invariant fails, or a candidate is emitted with a missing required field, the refresh task ends `partially_completed` or `failed`; it must not replace `current.json`. The previous completed snapshot remains readable with its own `as_of`; if it exceeds the configured freshness policy, return an explicit stale/unavailable state rather than false “today” data.

- [ ] **Step 6: Re-run the universe tests and add source-consistency tests.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_sector_universe.py -q`

Expected: every displayed row has same-day data and a persisted non-empty constituent list; incomplete candidates are absent and diagnosed.

### Task 3: Add bounded refresh orchestration and observable state

**Files:**
- Create: `backend/sector_refresh.py`
- Modify: `backend/app.py`
- Create: `backend/tests/test_sector_refresh.py`

**Interfaces:**
- Consumes: `build_verified_sector_snapshot`, `SectorSnapshotStore`, request id, and a bounded executor.
- Produces: `start_sector_refresh() -> dict`, `get_sector_refresh_status() -> dict`, `GET /api/sectors/status`, and `POST /api/sectors/refresh`.

- [ ] **Step 1: Write failing task-state tests.**

```python
def test_refresh_is_idempotent_while_running(tmp_path, monkeypatch):
    service = SectorRefreshService(SectorSnapshotStore(tmp_path))
    first = service.start("request-1")
    second = service.start("request-2")
    assert first["task_id"] == second["task_id"]
    assert second["status"] == "running"


def test_failed_refresh_keeps_previous_completed_snapshot(tmp_path, monkeypatch):
    service = SectorRefreshService(SectorSnapshotStore(tmp_path))
    service.store.publish({"snapshot_id": "old", "status": "completed", "sectors": []})
    monkeypatch.setattr(service, "build", lambda: (_ for _ in ()).throw(RuntimeError("upstream")))
    service.run_once("request-1")
    assert service.store.load_current()["snapshot_id"] == "old"
```

- [ ] **Step 2: Run the refresh tests and confirm they fail because the service does not exist.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_sector_refresh.py -q`

Expected: import failure for `sector_refresh`.

- [ ] **Step 3: Implement a single-worker, finite refresh service.**

Persist `task_id`, `request_id`, `status` (`pending`, `running`, `partially_completed`, `completed`, `failed`), current step, attempt count, start/update/end timestamps, data date, error type, error detail, snapshot id, candidate/published/rejected counts, and upstream call count. Limit to one worker, one retry only for TeaJoin network/HTTP 5xx errors, exponential backoff, a maximum run time, and a maximum provider-call budget. Parameter/contract errors and incomplete data are not retried.

- [ ] **Step 4: Wire explicit API behavior.**

`POST /api/sectors/refresh` starts or returns the in-flight task with HTTP 202. `GET /api/sectors/status` returns the persisted state. `GET /api/all-sectors` reads only a completed snapshot and returns HTTP 503 with machine-readable `sector_snapshot_unavailable` or `sector_snapshot_stale` when no qualified snapshot is available. Never call TeaJoin during this GET path.

- [ ] **Step 5: Re-run refresh tests.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_sector_refresh.py -q`

Expected: idempotency, failure preservation, and explicit state transitions pass.

### Task 4: Serve snapshot-consistent details and stocks

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/astock.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `SectorSnapshotStore.load_current()` and snapshot member data.
- Produces: compatible `GET /api/all-sectors`, `GET /api/sector-detail`, and `GET /api/sector-members` responses with `snapshot_id` and data metadata.

- [ ] **Step 1: Write failing API consistency tests.**

```python
def test_sector_list_detail_and_members_use_one_snapshot(monkeypatch):
    response = client.get("/api/all-sectors")
    first = response.json()["data"]["industries"][0]
    detail = client.get("/api/sector-detail", params={"kind": first["kind"], "code": first["code"]})
    members = client.get("/api/sector-members", params={"kind": first["kind"], "code": first["code"]})
    assert detail.json()["data"]["snapshot_id"] == response.json()["data"]["snapshot_id"]
    assert members.json()["data"]["snapshot_id"] == response.json()["data"]["snapshot_id"]
    assert members.json()["data"]["members"]


def test_all_sectors_never_returns_partial_or_unlabeled_data(monkeypatch):
    response = client.get("/api/all-sectors")
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert all(row["data_status"] == "complete" for row in response.json()["data"]["industries"] + response.json()["data"]["concepts"])
```

- [ ] **Step 2: Run the API tests and confirm they fail against the live-assembly implementation.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_api.py -k sector -q`

Expected: missing `snapshot_id`/`data_status`, or direct TeaJoin access from the existing member path.

- [ ] **Step 3: Replace direct list/detail/member reads with snapshot reads.**

Retire `teajoin_all_sectors`, `teajoin_sector_detail`, and `teajoin_sector_members` from public request paths after their logic is moved into the refresh builder. Maintain response arrays `industries` and `concepts`, while adding top-level `snapshot_id`, `retrieved_at`, `market`, `currency`, `timezone`, `frequency`, `method_version`, and `completeness`. Add `snapshot_id`, `as_of`, and `data_status="complete"` to every row. Return 404 only when code/kind is absent from the completed snapshot.

- [ ] **Step 4: Re-run API tests.**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_api.py -k sector -q`

Expected: list, detail, and members prove the same snapshot id and non-empty members.

### Task 5: Make the UI expose only complete daily data and honest refresh state

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/Sectors.tsx`
- Modify: `frontend/src/pages/SectorDetail.tsx`
- Modify: `frontend/tests/sector-data-contract.test.mjs`

**Interfaces:**
- Consumes: `AllSectorsData` with snapshot metadata and `SectorRefreshStatus`.
- Produces: sorted current-day industry/concept cards, stable deep links, constituent table/cards, and explicit unavailable/stale states.

- [ ] **Step 1: Write failing frontend contract tests.**

```javascript
test("sector UI labels one verified snapshot and does not render incomplete cards", () => {
  assert.match(api, /snapshot_id: string/);
  assert.match(api, /data_status: "complete"/);
  assert.match(sectors, /日线收盘数据/);
  assert.match(sectors, /api\.sectorRefreshStatus/);
  assert.match(detail, /snapshot_id/);
});
```

- [ ] **Step 2: Run the frontend test and confirm it fails on absent snapshot contract fields.**

Run: `cd frontend; node --test tests/sector-data-contract.test.mjs`

Expected: missing snapshot-status API/type assertions.

- [ ] **Step 3: Update types and list behavior.**

Add `close`, `as_of`, `snapshot_id`, `data_status`, provider metadata, and completeness metadata to the TypeScript interfaces. Sort industries and concepts by `pct_change` descending within their own type, instead of the current code-order sort. Do not render cards with null day fields. Change the footer from source claims to `数据交易日`, `采集时间`, `快照编号`, and `已校验板块数/候选板块数`.

- [ ] **Step 4: Update detail behavior.**

Show close, daily pct_change, net amount with its provider-documented unit, lead stock, company count, trading date, provider, and snapshot id. Render the persisted constituent list; remove the normal-path empty-members message because a public sector is guaranteed to have constituents. If the snapshot is stale/unavailable, show the returned state and a refresh action/status instead of cached or fabricated cards.

- [ ] **Step 5: Re-run frontend contract test and production build.**

Run: `cd frontend; node --test tests/sector-data-contract.test.mjs`

Expected: all sector contract tests pass.

Run: `cd frontend; npm run build`

Expected: TypeScript and Vite build exit 0.

### Task 6: Run real-source acceptance and release checks

**Files:**
- Modify: `backend/tests/test_teajoin.py`
- Create: `backend/tests/test_sector_live.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: real TeaJoin credentials only in the explicitly marked `live` test environment.
- Produces: auditable acceptance evidence and operator refresh instructions.

- [ ] **Step 1: Add an opt-in live acceptance test.**

```python
@pytest.mark.live
def test_live_snapshot_has_no_public_incomplete_sector():
    snapshot = sector_snapshot_store.load_current()
    assert snapshot["status"] == "completed"
    assert snapshot["as_of"]
    assert snapshot["completeness"]["candidate_count"] == (
        snapshot["completeness"]["published_count"] + snapshot["completeness"]["excluded_count"]
    )
    assert all(row["data_status"] == "complete" for row in snapshot["sectors"])
```

The refresh acceptance command must fail when any candidate cannot meet the member/data contract; do not weaken the assertion by accepting empty arrays or null values. Before enabling the gate, calibrate `company_num` versus active `ths_member` counts on the provider’s current universe and document the accepted provider rule if its count denotes a different population.

- [ ] **Step 2: Run non-live regression tests.**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests -m "not live" -q`

Expected: all regression tests pass.

- [ ] **Step 3: Run the live refresh and acceptance test once.**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_sector_live.py -m live -q`

Expected: completed snapshot with one as-of date, no public incomplete row, and a non-empty member set for every public sector.

- [ ] **Step 4: Document runtime operation and rollback.**

Document the refresh endpoint, status endpoint, provider cadence, expected duration/call budget, `VR_DATA_DIR` snapshot path, 503 behavior, and rollback procedure: repoint `current.json` atomically to the last completed snapshot; never edit a completed snapshot in place.

## Self-review

- Scope coverage: the plan covers real industry/concept definitions, same-day price fields, no public missing data, constituent persistence, detail visibility, search compatibility, data metadata, async execution, observability, tests, operational refresh, and rollback.
- Current-code defects addressed: mixed static/daily universes, null concept day fields, direct request-time membership reads, filtered single-member concepts, code-order display, and no persisted completeness state.
- Intentional exclusions: Eastmoney daily sector flows, Sina classifications, and unvalidated THS directory rows are excluded because their board identifiers or constituent contract do not match the chosen TeaJoin/THS snapshot.
