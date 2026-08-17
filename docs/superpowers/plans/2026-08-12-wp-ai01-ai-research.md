# WP-AI01 AI Research Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone `/ai-research` streaming research chat page that reuses the existing `/api/chat` client, configured model, Markdown/tool rendering, abort behavior, and persisted conversation behavior.

**Architecture:** Move only the reusable Ask AI conversation state into a focused hook and message renderer, leaving the existing Drawer shell intact. The new page owns only its wide layout, optional stock context, structured research-question buttons, and bottom composer. Question labels are sent temporarily while stable ids remain in the data model for the next Router work package.

**Tech Stack:** React 19, React Router, TypeScript, Tailwind, react-markdown, remark-gfm, Node test runner.

## Global Constraints

- Frontend only; do not modify financial APIs, `backend/chat.py`, `backend/tools.py`, or Debate behavior.
- Continue using `chatStream` and `/api/chat`; do not introduce model configuration or hidden prompts.
- Preserve AskAiButton behavior and existing persisted-history safety rules.
- Do not claim Research Router or institutional research capability.

---

### Task 1: Lock navigation, route and question contracts

**Files:**
- Create: `frontend/tests/ai-research-page.test.mjs`
- Create: `frontend/src/data/researchQuestions.ts`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx`

**Interfaces:**
- Produces `RESEARCH_QUESTIONS` entries with `id`, `label`, and `group`.
- Produces public route `/ai-research`, ordered between stock data and debate.

- [ ] Write the contract test for the 12 stable ids/labels, 6+6 grouping, navigation ordering, and retained `/debate` route.
- [ ] Run `npm --prefix frontend test -- --test-name-pattern "AI research"` and verify failure.
- [ ] Add the data module, route and navigation entry.
- [ ] Re-run the focused test and verify pass.

### Task 2: Reuse the existing conversation engine

**Files:**
- Create: `frontend/src/components/chat/usePersistentChat.ts`
- Create: `frontend/src/components/chat/ChatMessage.tsx`
- Modify: `frontend/src/components/ui/AskAiButton.tsx`
- Modify: `frontend/tests/ask-ai-persistence.test.mjs`

**Interfaces:**
- Produces `usePersistentChat({storageKey, context})` with messages, loading, error, send, clear, abort.
- Produces `ChatMessage` supporting Markdown, GFM tables, tool chips, and optional note saving.

- [ ] Extend contract tests to require shared hook/renderer usage by AskAiButton and AIResearch.
- [ ] Run focused persistence/Markdown tests and verify failure.
- [ ] Extract existing state logic without changing its storage, abort, incomplete-turn, or stream semantics.
- [ ] Run focused tests and verify pass.

### Task 3: Build the wide AI Research page

**Files:**
- Create: `frontend/src/pages/AIResearch.tsx`
- Test: `frontend/tests/ai-research-page.test.mjs`

**Interfaces:**
- Consumes optional `?code=300308`, existing `StockSearchInput`, shared chat hook/renderer and configured-AI flag.
- Sends the selected `question.label` in WP-AI01 while retaining `question.id` in click structure.

- [ ] Add page contract assertions for free chat, optional stock context, six default questions, expansion, label send, configured-AI fallback and bottom composer.
- [ ] Run focused test and verify failure.
- [ ] Implement the centered wide chat layout and optional stock selector/context.
- [ ] Run focused test and verify pass.

### Task 4: Verify scope and regressions

**Files:**
- Verify only; no backend files.

**Interfaces:**
- `/debate` and AskAiButton remain present and operational by contract.

- [ ] Run `npm --prefix frontend test` and record exact totals.
- [ ] Run `$env:GOMAXPROCS='2'; npm --prefix frontend run build` and record exit status and warnings.
- [ ] Run `git diff --name-only` and verify no backend, tools, Debate, or financial API file changed for WP-AI01.
