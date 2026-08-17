# WP-AI02 Research Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route AIResearch requests through a server-only base research policy and one of twelve whitelisted question prompts while preserving legacy AskAI behavior.

**Architecture:** A focused `backend/research` package owns the immutable policy, question registry, and deterministic lookup. The existing chat layer accepts optional research routing metadata and chooses either the legacy system prompt or the research prompt; the shared frontend chat transport adds optional metadata without changing existing callers.

**Tech Stack:** Python 3, FastAPI, pytest, TypeScript, React, Node test runner, Vite.

## Global Constraints

- Do not modify `backend/tools.py`, Debate, database schema, financial data APIs, or the chat UI design.
- Frontend sends only `research_mode` and a stable `research_question_id`; hidden prompts remain server-side.
- Invalid research IDs fail closed with HTTP 400 and `invalid_research_question_id`.
- Existing `/api/chat` callers remain backward compatible.

---

### Task 1: Server-side Research Registry and Router

**Files:**
- Create: `backend/research/__init__.py`
- Create: `backend/research/policy.py`
- Create: `backend/research/questions.py`
- Create: `backend/research/router.py`
- Test: `backend/tests/test_research_router.py`

**Interfaces:**
- Produces: `get_research_question(question_id: str) -> ResearchQuestion`
- Produces: `build_research_prompt(question_id: str | None) -> str`
- Raises: `InvalidResearchQuestionId`

- [ ] Write tests asserting base-only routing, two distinct prompt routes, invalid-ID rejection, all twelve IDs, and absence of the legacy five-dimension framework.
- [ ] Run `python -m pytest backend/tests/test_research_router.py -q` and verify failure because `research` does not exist.
- [ ] Add the base policy, twelve prompt records, and deterministic dictionary lookup without dynamic imports, paths, or `eval`.
- [ ] Re-run the focused test and verify all cases pass.

### Task 2: Backward-compatible Chat API Integration

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/chat.py`
- Test: `backend/tests/test_research_chat_api.py`

**Interfaces:**
- `ChatReq.research_mode: bool = False`
- `ChatReq.research_question_id: str | None = None`
- `run_chat_stream(..., research_mode: bool = False, research_question_id: str | None = None)`

- [ ] Write API and chat-layer tests for legacy fallback, research base mode, valid question routing, invalid-ID HTTP 400, and CLI/API stream prompt selection.
- [ ] Run the focused tests and verify expected signature/schema failures.
- [ ] Validate routing before creating `StreamingResponse`, then pass the optional fields through API and CLI chat paths.
- [ ] Re-run focused tests and verify all pass.

### Task 3: Frontend Research Metadata Transport

**Files:**
- Modify: `frontend/src/lib/llm.ts`
- Modify: `frontend/src/components/chat/usePersistentChat.ts`
- Modify: `frontend/src/pages/AIResearch.tsx`
- Test: `frontend/tests/ai-research-router.test.mjs`

**Interfaces:**
- `ChatRequestOptions { researchMode?: boolean; researchQuestionId?: string | null }`
- `usePersistentChat({ ..., researchMode?: boolean })`
- `send(text: string, options?: { researchQuestionId?: string | null })`

- [ ] Write source-contract tests proving free questions send research mode, buttons send stable IDs, and AskAI sends neither research field nor hidden prompts.
- [ ] Run the focused frontend test and verify it fails on missing metadata transport.
- [ ] Add optional request serialization and pass IDs only from AIResearch button clicks while the visible message remains the label.
- [ ] Re-run the focused test and full frontend suite.

### Task 4: Release Verification

**Files:**
- Verify only; no production changes unless a failing check reveals a scoped defect.

- [ ] Run backend focused tests and the non-live backend suite.
- [ ] Run `npm test` and record pass/fail counts.
- [ ] Run `npm run build` and record TypeScript/Vite results.
- [ ] Run `git diff --check` on WP-AI02 files and confirm `backend/tools.py` and `frontend/src/pages/Debate.tsx` are untouched by this work order.
