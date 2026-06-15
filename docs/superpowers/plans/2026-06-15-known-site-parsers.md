# Known Site Parsers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class `known_site` source support for `https://claude.com/blog` and `https://www.anthropic.com/engineering`.

**Architecture:** Discovery recognizes exact known listing URLs and stores `strategy_kind="known_site"` with a parser id in `strategy_config`. Source sync dispatches known-site strategies to site-specific parsers that extract post URL, title, publication date, and article text into existing `ParsedPost` objects so persistence and analysis stay unchanged.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, stdlib `HTMLParser`, pytest.

---

### Task 1: Discovery Contract

**Files:**
- Modify: `backend/app/parsing/discovery.py`
- Test: `backend/tests/unit/test_source_discovery.py`
- Test: `backend/tests/api/test_sources_api.py`

- [ ] Add tests proving `https://claude.com/blog` and `https://www.anthropic.com/engineering` discover as `known_site`, have no `feed_url`, and use parser ids `claude_blog` and `anthropic_engineering`.
- [ ] Add an API test proving onboarding returns `status="ready"` and `needs_readaptation=false` for a known site.
- [ ] Implement an exact URL registry in discovery before network fetch/feed probing.
- [ ] Update onboarding so `known_site` is treated as ready, like `feed`.

### Task 2: Known Site Sync Parsers

**Files:**
- Create: `backend/app/parsing/known_sites.py`
- Modify: `backend/app/services/source_sync.py`
- Test: `backend/tests/unit/test_source_sync.py`

- [ ] Add tests for Claude Blog and Anthropic Engineering sync using representative listing/article HTML.
- [ ] Implement parser helpers that extract listing links, listing dates, article first text, and article metadata dates.
- [ ] Wire `strategy_kind="known_site"` in `_load_posts_for_source`.
- [ ] Ensure persisted posts have title, canonical URL, date, raw text, `source_strategy="known_site"`, and date source metadata.

### Task 3: Verification, Review, Delivery

**Files:**
- All touched files.

- [ ] Run focused backend tests for discovery, API sources, and source sync.
- [ ] Run a subagent code review against the branch diff and fix Critical/Important findings.
- [ ] Repeat review if fixes are required.
- [ ] Run final verification.
- [ ] Commit all tracked changes on `codex/known-site-parsers`.
- [ ] Push the branch and open a pull request.
