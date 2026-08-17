# Production Readiness 500 Prevention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent database-schema and missing-sector-snapshot failures from reaching production traffic as opaque HTTP 500 responses.

**Architecture:** Keep PostgreSQL as the durable source for user data and add one named Docker volume for the already file-backed sector snapshot store. API readiness will require a complete, fresh-enough verified snapshot; deployment will run Alembic as an explicit one-shot prerequisite before starting the API and gateway.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Docker Compose, pytest.

## Global Constraints

- Do not place TeaJoin or any production key in code, tests, image layers, or logs.
- Preserve current public API response contracts except readiness correctly returns 503 when a required dependency is unavailable.
- Use versioned Alembic migrations only; this change adds no schema migration.
- Sector data remains an immutable verified snapshot; no partial snapshot may be served.

---

### Task 1: Persist sector snapshots across API replacement

**Files:**
- Modify: `compose.production.yaml`
- Modify: `compose.demo.yaml`
- Test: `deploy/tests/test_deploy_scripts.py`

**Interfaces:**
- Produces `VR_DATA_DIR=/data/runtime` and a `sector_data` named volume mounted at that path for API containers.

- [ ] Write a failing deployment-contract test asserting `sector_data` and `VR_DATA_DIR=/data/runtime` are present.
- [ ] Run `pytest deploy/tests/test_deploy_scripts.py -q` and observe failure.
- [ ] Mount `sector_data:/data/runtime` in production and demo API services; declare the named volume; set `VR_DATA_DIR=/data/runtime` in their environment.
- [ ] Run the deployment-contract test and observe pass.

### Task 2: Fail readiness when sector data is missing or stale

**Files:**
- Modify: `backend/sector_refresh.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_readiness.py`

**Interfaces:**
- Produces `SectorRefreshService.readiness()` returning `{ok: bool, reason?: str, snapshot_id?: str, as_of?: str}`.
- `/api/ready` returns 503 when `readiness().ok` is false.

- [ ] Write failing tests for missing and stale snapshot readiness.
- [ ] Run `pytest backend/tests/test_readiness.py -q` and observe failure.
- [ ] Implement date-aware snapshot readiness using Asia/Shanghai trading-day metadata and reject missing, incomplete, or stale snapshots.
- [ ] Make `/api/ready` include that readiness decision and return 503 before gateway accepts traffic.
- [ ] Run readiness tests and observe pass.

### Task 3: Enforce migration before API release

**Files:**
- Modify: `compose.production.yaml`
- Modify: `compose.demo.yaml`
- Test: `deploy/tests/test_deploy_scripts.py`

**Interfaces:**
- API `depends_on` a successful one-shot `migrate` service.
- `migrate` is included in normal Compose startup rather than hidden behind a profile.

- [ ] Write a failing deployment-contract test for an unprofiled migration service and successful API dependency.
- [ ] Run the deployment-contract test and observe failure.
- [ ] Remove the migration profile and add `migrate: {condition: service_completed_successfully}` under each API service.
- [ ] Validate Compose syntax and run deployment-contract tests.

### Task 4: Validate and document the release path

**Files:**
- Modify: `deploy/OPERATIONS.md`
- Test: `backend/tests/test_public_runtime_security.py`
- Test: `deploy/tests/test_release_gate.py`

- [ ] Add tests for startup configuration validation and release deployment contracts.
- [ ] Run the targeted tests and observe the expected failures.
- [ ] Validate database URL during production startup and document the migration-first, snapshot-ready release check.
- [ ] Run full backend tests, deployment tests, frontend tests, and `docker compose config` for demo and production manifests.
