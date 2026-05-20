# Reload Posts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `Refresh post dates` with a destructive `Reload posts` action that reloads only the last 2 months of posts for a source.

**Architecture:** Add a dedicated backend reload service that deletes recent posts for one source, then reparses and persists that source without the normal incremental sync cutoff. Update the sources UI to rename the action, show a warning, and call the new API.

**Tech Stack:** FastAPI, SQLAlchemy, React, Vitest, Testing Library, Pytest

---

### Task 1: Backend reload service and route

**Files:**
- Modify: `backend/app/services/source_sync.py`
- Modify: `backend/app/api/routes/sources.py`
- Test: `backend/tests/unit/test_source_sync.py`
- Test: `backend/tests/api/test_sources_api.py`

- [ ] Add failing backend tests for recent-window deletion and reload counts.
- [ ] Run the targeted pytest selection and verify the new tests fail for the expected missing behavior.
- [ ] Implement the minimal reload service and route.
- [ ] Re-run the targeted pytest selection and verify it passes.

### Task 2: Frontend rename and warning flow

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/SourcesPage.tsx`
- Test: `frontend/src/test/sources-page.test.tsx`

- [ ] Add a failing frontend test for `Reload posts`, the confirmation warning, and the new API call.
- [ ] Run the targeted frontend test and verify it fails for the expected missing behavior.
- [ ] Implement the minimal UI/API changes.
- [ ] Re-run the targeted frontend test and verify it passes.

### Task 3: Full verification

**Files:**
- No new files expected

- [ ] Run the relevant backend test files.
- [ ] Run the relevant frontend test file.
- [ ] Manually verify the reload behavior against the local app/API if possible.
- [ ] Commit only the intended files.
