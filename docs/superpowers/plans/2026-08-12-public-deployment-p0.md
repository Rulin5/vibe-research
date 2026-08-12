# Public Deployment P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the application fail closed in public mode and provide a deployable HTTPS, rate-limited, observable production topology without adding CAPTCHA.

**Architecture:** Keep local development compatible with the current FastAPI + Vite flow. Add a typed runtime security policy that is permissive only in explicit `local` mode and validates mandatory public controls at startup. Public traffic terminates at Nginx, which serves the compiled frontend and proxies only `/api`; the API remains private to the compose network and uses Redis for distributed request limits.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Redis, Nginx, Docker Compose, React 19/Vite, Node test runner, pytest, npm audit.

## Global Constraints

- CAPTCHA, SMS verification, and third-party human-verification services are out of scope.
- Public mode must never start with insecure cookies, wildcard/no origins, missing Redis, arbitrary model endpoints, or unscanned report uploads.
- Local mode remains available on loopback for existing development and local model endpoints.
- AI and public-data calls remain bounded; no financial recommendation, order routing, or asset-allocation personalisation is introduced.
- API keys, passwords, uploaded-file contents, and private holdings must never enter logs.

---

### Task 1: Runtime policy and server-side request controls

**Files:**
- Create: `backend/runtime_security.py`
- Modify: `backend/app.py`
- Modify: `backend/auth.py`
- Modify: `backend/chat.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_runtime_security.py`

**Interfaces:**
- `runtime_security.settings() -> RuntimeSecuritySettings` exposes `mode`, `is_public`, `allowed_origins`, `ai_allowed_hosts`, and `redis_url`.
- `runtime_security.enforce_startup_policy() -> None` raises before serving an unsafe public configuration.
- `runtime_security.enforce_rate_limit(request, scope, limit, window_seconds, user_id=None) -> None` raises HTTP 429 with `Retry-After` when Redis counters exceed the policy.

- [x] Write failing tests for public-mode startup rejection when `VR_COOKIE_SECURE`, `VR_REDIS_URL`, `VR_AI_ALLOWED_HOSTS`, or `VR_REPORT_SCAN_COMMAND` is absent; verify local mode is accepted.
- [x] Implement a cached settings parser. Accept only `local` and `public`; reject any other value. In public mode require `VR_COOKIE_SECURE=true`, explicit HTTPS origins, a non-empty Redis URL, non-empty AI hostname allowlist, and a report scan command.
- [x] Add a Redis fixed-window limiter with keys `vr:limit:{scope}:{identity}:{window}`. Rate-limit registration (5/hour/IP), login (10/15 minutes/IP), uploads (20/hour/user), chat/debate/reflect (30/hour/user), and all unauthenticated public-data routes (120/minute/IP). Return 503 rather than silently disabling limits when public Redis fails.
- [x] Make `cookie_secure()` derive from validated public mode; retain an explicit local override only in local mode.
- [x] Replace the hard-coded chat public-mode flag with settings. In public mode require HTTPS and an administrator allowlisted hostname for user model endpoints, resolve the hostname, reject all private/link-local/metadata addresses, and set `allow_redirects=False` on model requests.
- [x] Run focused runtime and auth tests before and after implementation.

### Task 2: Production HTTP boundary and upload safety gate

**Files:**
- Create: `deploy/nginx/default.conf`
- Create: `deploy/Dockerfile.backend`
- Create: `deploy/Dockerfile.frontend`
- Create: `compose.production.yaml`
- Modify: `backend/report_storage.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_reports_and_security.py`

**Interfaces:**
- Nginx serves `/` from the compiled frontend, proxies `/api/` to the private API service, enforces request-size and edge rate limits, and sets forwarding/security headers.
- `report_storage.scan_report(path: Path) -> None` invokes the configured scanner and rejects non-zero exits in public mode.

- [x] Write a failing report-storage test that public mode rejects a write when the scanner fails and never creates metadata for the rejected file.
- [x] Add scanner execution after atomic temporary-file creation and before database commit; use argument arrays, a finite timeout, no shell interpolation, and delete temporary files on every failure.
- [x] Add Nginx TLS-only configuration with HSTS, CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and IP edge limits. The HTTP cap is 36 MB so a valid 25 MB binary can survive base64 expansion; the API retains the exact 25 MB decoded-file cap.
- [x] Add production compose services for Nginx/frontend build, API, Redis, PostgreSQL, and ClamAV, all on a private network except Nginx. Mount reports and PostgreSQL volumes explicitly; bind only ports 80/443 at the host.
- [x] Add API startup/liveness and readiness endpoints. Readiness checks the database and Redis in public mode without reaching market data providers.

### Task 3: Observability, release artifacts, and dependency remediation

**Files:**
- Create: `backend/observability.py`
- Modify: `backend/app.py`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `deploy/production.env.example`
- Create: `deploy/OPERATIONS.md`
- Test: `backend/tests/test_observability.py`
- Test: `frontend/tests/security-contract.test.mjs`

**Interfaces:**
- Every API response carries `X-Request-ID`; logs contain only request ID, route, method, status, duration, and a pseudonymous user identifier.
- `GET /api/ready` returns 200 only when required dependencies are usable.

- [x] Write failing tests for request-ID propagation and log redaction of secret-bearing headers.
- [x] Add JSON structured request logging middleware with no request-body logging and a stable pseudonymous user fingerprint.
- [x] Upgrade `react-router-dom` and its lockfile-resolved dependencies to a version outside the audited vulnerable range, then add a contract test that prevents a downgrade into the vulnerable range.
- [x] Document exact production environment variable names, secret rotation constraints, schema migration command, rollback constraints, PostgreSQL backup schedule, alert thresholds, and an incident procedure. Do not put real secrets in any repository file.
- [ ] Run frontend tests/build, focused backend tests, dependency audit, compose configuration validation, and an HTTPS reverse-proxy smoke test in a non-production environment.

### Task 4: Release decision gate

**Files:**
- Create: `deploy/RELEASE_CHECKLIST.md`

- [ ] Require an independently provisioned PostgreSQL and Redis service, a valid certificate, verified backup restore, explicit market-data/TeaJoin public-use authorization, privacy/service/risk disclosures, and a security review before public DNS is enabled.
- [x] Record that the later personal-suitability/allocation feature remains disabled until its own financial-compliance and user-data-isolation release gate is completed.
- [x] Mark a public release blocked when any required configuration, test, dependency audit, backup restore, provider authorization, or security sign-off is absent.
