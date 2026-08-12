# Release Readiness Work Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make backend tests independent from user data, support lossless AI credential-key rotation, automate production-stack verification, and turn monitoring/compliance requirements into enforceable release gates.

**Architecture:** Keep the existing modular FastAPI application and Compose topology. Add a dedicated disposable PostgreSQL test service with fail-closed database-name validation; add current/previous encryption-key support with transactional re-encryption; add repeatable PowerShell deployment drills; expose internal Prometheus metrics and validate external sign-offs through a machine-readable evidence manifest that defaults to blocked.

**Tech Stack:** Python 3.11+, pytest, PostgreSQL 17, SQLAlchemy/Alembic, Fernet, Docker Compose, PowerShell 7/Windows PowerShell, Prometheus.

## Global Constraints

- Never run destructive test cleanup unless the selected database name ends with `_test`.
- Never print database passwords, API keys, encrypted secrets, decrypted secrets, cookies, or private holdings.
- `VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS` is temporary; it may be removed only after the bulk rotation command reports zero failures and zero remaining old-key rows.
- CAPTCHA remains out of scope.
- Real TLS validity, provider authorization, legal approval, security sign-off, and production restore evidence must remain blocked until supplied by authorized humans or target infrastructure.
- No schema change is required for key rotation; do not add a migration without a demonstrated data-contract need.

---

### Task 1: Fully isolated PostgreSQL test runtime

**Files:**
- Create: `compose.test.yaml`
- Modify: `backend/conftest.py`
- Create: `backend/tests/test_test_database_guard.py`
- Create: `deploy/scripts/run-backend-tests.ps1`
- Modify: `backend/.env.example`

**Interfaces:**
- `test_database.resolve_test_database_url() -> str` returns only a PostgreSQL URL whose database ends with `_test`.
- `test_database.clean_test_database() -> None` truncates application tables only after the suffix guard passes.
- `run-backend-tests.ps1` starts the disposable database, runs Alembic and `pytest -m "not live"`, and preserves the container on failure for diagnosis.

- [x] Write failing tests proving a production database name is rejected and an explicit `_test` URL is accepted.
- [x] Run the guard test and confirm failure because the module does not exist.
- [x] Implement the URL guard and configure pytest before application imports.
- [x] Add a PostgreSQL-only test Compose service on host port 55432 with a named test volume and non-production credentials.
- [x] Add authenticated per-test user cleanup through the shared test fixture; database-wide destructive cleanup was intentionally omitted because unique identities plus cascading user deletion provide isolation without truncating shared migration state.
- [x] Run all non-live backend tests against the disposable database and repair isolation-dependent failures without weakening assertions.

### Task 2: Lossless dual-key AI credential rotation

**Files:**
- Modify: `backend/ai_credentials.py`
- Modify: `backend/runtime_security.py`
- Create: `backend/rotate_ai_credentials.py`
- Create: `backend/tests/test_ai_key_rotation.py`
- Modify: `backend/.env.example`
- Modify: `deploy/production.env.example`

**Interfaces:**
- `ai_credentials.decrypt_secret(db, credential) -> tuple[str, bool]` decrypts with current key first, then previous key, and re-encrypts with current key when previous succeeds.
- `ai_credentials.rotate_all_credentials(db) -> dict[str, int]` atomically returns `total`, `rotated`, `current`, and `failed`; it never returns row identifiers or secret material.
- `python rotate_ai_credentials.py` exits non-zero if any stored credential cannot be decrypted.

- [x] Write failing tests for previous-key fallback, lazy re-encryption, wrong-key rejection, and an atomic bulk rotation summary.
- [x] Run the focused tests and confirm failure because dual-key APIs do not exist.
- [x] Implement current/previous ciphers, lazy re-encryption, and atomic bulk rotation.
- [x] Require different current/previous values in public mode when previous is configured.
- [x] Document and test the exact add-current/retain-previous/rotate/remove-previous sequence.

### Task 3: Repeatable TLS, malware-scan, image, backup and restore drills

**Files:**
- Create: `deploy/scripts/new-staging-certificate.ps1`
- Create: `deploy/scripts/verify-stack.ps1`
- Create: `deploy/scripts/backup.ps1`
- Create: `deploy/scripts/restore-drill.ps1`
- Create: `deploy/tests/test_deploy_scripts.py`
- Modify: `deploy/OPERATIONS.md`

**Interfaces:**
- Scripts accept explicit Compose/env/certificate/backup paths and resolve them before any write or restore.
- `verify-stack.ps1` verifies Compose health, HTTPS, security headers, API readiness, and operator-supplied EICAR rejection evidence.
- `restore-drill.ps1` restores only into a database ending `_restore_test`, runs row/table checks, and records a timestamped evidence JSON without secrets.

- [x] Write static contract tests for explicit parameters, safe database suffixes, HTTPS checks, EICAR input, and evidence output.
- [x] Implement staging certificate generation without treating it as public-trust evidence.
- [x] Implement backup and restore drill scripts with exact-path validation and fail-closed suffix checks.
- [x] Implement stack verification and evidence JSON generation.
- [x] Build available images and run every locally possible drill; record Docker registry/network failures as blocked evidence rather than success.

### Task 4: Internal metrics, alert rules, and enforceable release evidence

**Files:**
- Create: `backend/metrics.py`
- Modify: `backend/app.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_metrics.py`
- Create: `deploy/monitoring/prometheus.yml`
- Create: `deploy/monitoring/alerts.yml`
- Modify: `deploy/nginx/default.conf`
- Modify: `compose.production.yaml`
- Create: `deploy/release-evidence.example.json`
- Create: `deploy/scripts/check_release_gate.py`
- Create: `deploy/tests/test_release_gate.py`
- Create: `deploy/compliance/DATA_PROVIDER_AUTHORIZATION.md`
- Create: `deploy/compliance/SECURITY_SIGNOFF.md`
- Create: `deploy/compliance/PRIVACY_AND_FINANCIAL_DISCLOSURES.md`
- Modify: `deploy/RELEASE_CHECKLIST.md`

**Interfaces:**
- `GET /api/metrics` returns Prometheus text internally; Nginx returns 404 for the public route.
- Metrics include request count/status, latency, in-progress requests, and dependency readiness.
- `check_release_gate.py --evidence <path>` exits 0 only when every required item is approved, unexpired where applicable, and references an existing evidence file.

- [x] Write failing metrics tests and release-gate tests for missing, false, path-escape, and complete evidence.
- [x] Implement low-cardinality metrics without usernames, raw paths containing IDs, query strings, or secrets.
- [x] Add Prometheus and alert rules for API availability, 5xx ratio, latency, readiness, and scrape failure; keep monitoring ports private.
- [x] Implement evidence validation with all external approvals false by default.
- [x] Run backend tests, frontend tests/build, dependency audit, Compose validation, script contract tests, and local health/metrics smoke tests.

## Completion Rule

Code may be marked implemented when automated tests pass. Public release remains blocked until valid TLS, production image build, EICAR rejection, production-like restore drill, provider authorization, security sign-off, and privacy/financial disclosure evidence all pass the release-gate checker.
