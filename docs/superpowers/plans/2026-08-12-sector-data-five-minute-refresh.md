# Sector Data Five-Minute Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the sector center publish the complete usable TeaJoin sector universe, refresh its market summary at most once every five minutes, and keep the last non-empty snapshot readable while a refresh is running or failing.

**Architecture:** TeaJoin/Tushare remains the only supplier for this page. `moneyflow_ind_ths` and `moneyflow_cnt_ths` provide the dated sector summary; `ths_member` provides the normalized constituent list. A mismatch between the summary's reported company count and the valid constituent list is recorded as audit metadata instead of deleting the sector. The scheduler refreshes every 300 seconds, reuses same-day constituent lists, and atomically publishes only a complete non-empty snapshot.

**Tech Stack:** Python 3, FastAPI, pytest, React, TypeScript, Node test runner, Docker Compose.

## Global Constraints

- Do not modify AI research, financial tools, or unrelated modules.
- Do not expose or log the TeaJoin API key.
- Public reads must never observe a partially written or empty refreshing snapshot.
- Five minutes is the minimum refresh interval; supplier failures retain the previous published snapshot.
- Preserve the existing `/api/all-sectors`, `/api/sector-detail`, and `/api/sector-members` response compatibility; new metadata is additive.

---

### Task 1: Correct sector-universe completeness accounting

**Files:**
- Modify: `backend/astock.py`
- Test: `backend/tests/test_sector_universe.py`

**Interfaces:**
- Consumes: TeaJoin `moneyflow_ind_ths`, `moneyflow_cnt_ths`, and `ths_member` responses.
- Produces: `build_verified_sector_snapshot(trade_date, reusable_members=None) -> (snapshot, member_map)`.

- [ ] Add a failing test proving a reported/member count mismatch retains the sector and records the variance.
- [ ] Add a failing test proving reusable same-day member data avoids another `ths_member` call.
- [ ] Run `python -m pytest backend/tests/test_sector_universe.py -q` and confirm the new tests fail for the missing behavior.
- [ ] Use valid normalized `ths_member` rows as the displayed `member_count`, preserve `provider_member_count`, and add mismatch audit counters.
- [ ] Keep empty constituent lists excluded and preserve completeness accounting.
- [ ] Re-run the focused test file and confirm it passes.

### Task 2: Enforce five-minute refresh with stale snapshot availability

**Files:**
- Modify: `backend/sector_refresh.py`
- Modify: `backend/sector_scheduler.py`
- Modify: `backend/sector_snapshot.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_sector_refresh.py`
- Test: `backend/tests/test_sector_snapshot.py`
- Test: `backend/tests/test_api.py`
- Test: `backend/tests/test_readiness.py`

**Interfaces:**
- Consumes: current atomic sector snapshot and its member map.
- Produces: refresh state plus readiness metadata with `stale` visibility while retaining `ok=true` for a complete older snapshot.

- [ ] Add failing tests for the 300-second interval, repeated polling, same-day member reuse, and serving a complete stale snapshot.
- [ ] Confirm focused failures before implementation.
- [ ] Load the current member map once and pass it only to the production builder for same-day reuse.
- [ ] Make readiness reject missing/corrupt/empty snapshots but allow a complete older snapshot with `stale=true`.
- [ ] Keep atomic publish behavior so failed refreshes never replace the current pointer.
- [ ] Re-run focused backend tests.

### Task 3: Expose freshness and deploy the interval

**Files:**
- Modify: `compose.production.yaml`
- Modify: `compose.demo.yaml`
- Modify: `deploy/OPERATIONS.md`
- Modify: `deploy/tests/test_deploy_scripts.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/Sectors.tsx`
- Test: `frontend/tests/sector-data-contract.test.mjs`

**Interfaces:**
- Consumes: additive `stale` and refresh metadata from `/api/all-sectors`.
- Produces: visible data timestamp/counts without clearing the page during refresh.

- [ ] Add contract tests for the exact 300-second deployment interval and stale-data indicator.
- [ ] Confirm the new tests fail.
- [ ] Set both Compose schedulers to 300 seconds and document the stale-while-refresh contract.
- [ ] Display the last successful retrieval time and a delayed-data notice without hiding existing cards.
- [ ] Re-run frontend and deploy contract tests.

### Task 4: Verification

**Files:**
- Verify all modified files only; no new production dependencies.

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: reproducible release evidence.

- [ ] Run focused sector backend tests.
- [ ] Run all backend tests excluding explicit live tests.
- [ ] Run frontend tests.
- [ ] Run the frontend production build.
- [ ] Run deployment tests and `git diff --check`.
- [ ] If credentials and supplier availability permit, build one real snapshot and report actual published industry/concept counts without printing the key.
