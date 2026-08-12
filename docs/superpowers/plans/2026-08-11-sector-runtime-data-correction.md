# Sector Runtime Data Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the visible board center is served by the current TeaJoin daily-industry implementation instead of stale local backend processes.

**Architecture:** The current frontend development proxy targets port 8900. Existing listeners on 8900-8903 predate the daily-industry implementation, so a clean, isolated backend instance will be started on 8904 and verified through its HTTP API before any running user process is touched.

**Tech Stack:** FastAPI, Uvicorn, TeaJoin/Tushare, Vite proxy.

## Global Constraints

- Never stop an existing user-owned process without explicit authorization.
- Daily industry data must expose the actual provider trading date and never claim to be real-time.
- API keys remain in ignored runtime configuration, never in source or command output.

---

### Task 1: Prove the stale-runtime mismatch

**Files:**
- Inspect: `frontend/vite.config.ts`
- Inspect: active local FastAPI listeners on ports 8900-8903

**Interfaces:**
- Consumes: `GET /api/all-sectors`
- Produces: evidence of proxy target and active response schemas.

- [ ] Request `/api/all-sectors` from every active backend listener.
- [ ] Confirm the Vite proxy target.
- [ ] Record the mismatch between active response data and the current source contract.

### Task 2: Start and verify the current backend safely

**Files:**
- Run: `backend/app.py`

**Interfaces:**
- Consumes: `TEAJOIN_API_KEY` from `backend/.env`
- Produces: `GET /api/all-sectors` with `source`, `as_of`, industry day returns, and compatible member lookup.

- [ ] Start the current backend on `127.0.0.1:8904` without stopping existing listeners.
- [ ] Request `/api/all-sectors` and assert a nonempty current `as_of`, 90 daily industry rows, and null concept day returns.
- [ ] Request `/api/sector-members` for the returned first industry and assert nonempty real constituents.

### Task 3: Provide a safe frontend verification route

**Files:**
- Run: `frontend/vite.config.ts`

**Interfaces:**
- Consumes: `VITE_API_URL=http://127.0.0.1:8904`
- Produces: Vite proxy routing `/api` to the verified current backend.

- [ ] Start a separate Vite development server on port 5900 with the explicit verified backend target.
- [ ] Confirm `http://127.0.0.1:5900/api/all-sectors` contains the current daily-industry response.
