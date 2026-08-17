# Public Data Always Available Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure public dashboard requests always read a previously published complete snapshot and never wait for upstream collection or render empty during refresh.

**Architecture:** A deployment bootstrap builds a complete persistent snapshot for the six Daily Review datasets before the API and gateway start. A dedicated scheduler refreshes it outside HTTP; publication is atomic, and any failed or incomplete refresh preserves the last successful snapshot. Existing sector snapshots remain unchanged.

**Tech Stack:** FastAPI, Python filesystem snapshots, Docker Compose, pytest.

## Global Constraints

- HTTP public dashboard handlers must not call TeaJoin, Eastmoney, Tencent, or AkShare.
- A missing complete snapshot blocks deployment readiness instead of exposing an empty UI.
- Refresh failure must preserve and serve the previous complete snapshot without an age cutoff.
- No production key may be stored in code, image layers, logs, or tests.

---

### Task 1: Persistent complete public-data snapshot

**Files:**
- Create: `backend/public_data_snapshot.py`
- Create: `backend/tests/test_public_data_snapshot.py`

**Interfaces:**
- Produces `PublicDataSnapshotStore.publish(payload)`, `load_current()`, and cross-process refresh locking.

- [ ] Write tests that reject incomplete data and preserve the previous snapshot after a failed build.
- [ ] Run the tests and observe failure because the store does not exist.
- [ ] Implement atomic versioned snapshot publication and shared refresh locking.
- [ ] Run the tests and observe pass.

### Task 2: Bootstrap and periodic refresh

**Files:**
- Create: `backend/public_data_refresh.py`
- Create: `backend/public_data_bootstrap.py`
- Create: `backend/public_data_scheduler.py`
- Create: `backend/tests/test_public_data_refresh.py`

**Interfaces:**
- Produces `PublicDataRefreshService.run_once(request_id)` and `readiness()`.
- Consumes the existing market, index and quote adapters only from background processes.

- [ ] Write tests for complete publication, incomplete rejection, stale fallback and bootstrap failure.
- [ ] Run the tests and observe failure.
- [ ] Implement collection, validation, atomic publication and scheduler loop.
- [ ] Run the tests and observe pass.

### Task 3: Snapshot-only API reads

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_readiness.py`

**Interfaces:**
- Existing endpoint response bodies remain compatible.
- `/api/ready` requires a complete public dashboard snapshot.

- [ ] Write endpoint tests that make every upstream adapter raise and still receive snapshot data.
- [ ] Run tests and observe failure from current on-request upstream calls.
- [ ] Route the six dashboard endpoints to the persistent store and extend readiness.
- [ ] Run tests and observe pass.

### Task 4: Deployment ordering and verification

**Files:**
- Modify: `compose.production.yaml`
- Modify: `compose.demo.yaml`
- Modify: `deploy/scripts/release.ps1`
- Modify: `deploy/OPERATIONS.md`
- Modify: `deploy/tests/test_deploy_scripts.py`

**Interfaces:**
- API starts only after `public-data-bootstrap` succeeds.
- `public-data-scheduler` shares the snapshot volume and refreshes outside request traffic.

- [ ] Write deployment-contract tests for bootstrap ordering, shared volume and scheduler.
- [ ] Run tests and observe failure.
- [ ] Add services and release ordering, then document stale-serving behavior.
- [ ] Run backend/deployment tests, frontend tests, build, and both Compose config checks.
