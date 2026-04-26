# Good News MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the phase-1 local-first Good News MVP: source onboarding, scheduled ingestion, Russian AI summaries, hybrid ranking, email digests, feedback capture, settings, digest history, and Grafana-backed observability.

**Architecture:** Use a single FastAPI backend to own API, scheduler, ingestion, ranking, digest generation, settings, and secret access. Use a React + Vite frontend for the six user-facing screens. Run PostgreSQL, Ollama, Grafana, Prometheus, Loki, OpenTelemetry Collector, and grafana-image-renderer with Docker Compose so every slice stays runnable locally.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, APScheduler, httpx, feedparser, BeautifulSoup4, cryptography, PostgreSQL 16, React 18, Vite, TypeScript, React Router, TanStack Query, React Hook Form, Docker Compose, Ollama, Grafana OSS, Prometheus, Loki, OpenTelemetry Collector

---

## Working Rules

- Run all commands from `C:\Users\ytype\dev\projects\good-news`.
- Use PowerShell commands as written below.
- Keep each task shippable: after every task, the app should still boot and tests for that slice should pass.
- Do not add vector search, video ingestion, multi-user auth, or a custom observability UI.
- Keep ranking inspectable and deterministic-first parsing ahead of AI assistance.

## Planned Repository Layout

- `docker-compose.yml`: local orchestration for app and observability services.
- `.env.example`: non-secret local configuration keys only.
- `backend/pyproject.toml`: Python dependencies and pytest settings.
- `backend/alembic.ini` and `backend/alembic/`: database migrations.
- `backend/app/main.py`: FastAPI app factory and startup hooks.
- `backend/app/api/routes/`: `health.py`, `sources.py`, `posts.py`, `settings.py`, `feedback.py`, `digests.py`, `preferences.py`.
- `backend/app/core/`: `config.py`, `db.py`, `secrets.py`, `logging.py`, `telemetry.py`.
- `backend/app/models/`: SQLAlchemy models for `sources`, `posts`, `post_analysis`, `feedback`, `digests`, `digest_items`, `settings`, `secret_settings`, `preference_profile`, `technical_events`.
- `backend/app/schemas/`: request and response DTOs for API routes.
- `backend/app/services/`: `source_onboarding.py`, `source_readaptation.py`, `source_sync.py`, `analysis.py`, `ranking.py`, `preferences.py`, `digest_service.py`, `email_service.py`, `settings_service.py`, `observability_report.py`.
- `backend/app/parsing/`: deterministic feed discovery and HTML fallback strategy code.
- `backend/app/ai/ollama_client.py`: local model wrapper.
- `backend/app/jobs/`: APScheduler wiring for source sync, digests, catch-up, and observability report jobs.
- `backend/tests/`: unit and API tests.
- `frontend/package.json` and `frontend/vite.config.ts`: frontend tooling.
- `frontend/src/app/`: app shell and router.
- `frontend/src/lib/`: API client and shared types.
- `frontend/src/components/`: reusable UI pieces for posts, sources, settings, digests, and profile summaries.
- `frontend/src/pages/`: `FeedPage.tsx`, `WantToReadPage.tsx`, `DigestsPage.tsx`, `SourcesPage.tsx`, `SettingsPage.tsx`, `PreferenceProfilePage.tsx`.
- `frontend/src/test/`: Vitest and Testing Library coverage.
- `infra/prometheus/`, `infra/loki/`, `infra/otel/`, `infra/grafana/`: observability configuration.
- `scripts/bootstrap.ps1`: local setup for Python, Node, Docker, and initial migrations.
- `scripts/pull-ollama-model.ps1`: fetch the chosen local model.
- `backend/app/email/templates/`: `daily_digest.html.jinja2`, `observability_digest.html.jinja2`.
- `README.md`: setup and run instructions.

## Incremental Delivery Slices

### Task 1: Bootstrap the repo and ship a health-check slice

**Files:**
- Create: `.gitignore`, `.env.example`, `docker-compose.yml`
- Create: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/api/routes/health.py`, `backend/tests/unit/test_health.py`
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/app/AppShell.tsx`, `frontend/src/main.tsx`, `frontend/src/test/app-shell.test.tsx`
- Create: `scripts/bootstrap.ps1`, `README.md`

- [ ] Initialize the repo structure and tooling: `git init`, `New-Item -ItemType Directory -Force backend\app\api\routes,backend\tests\unit,frontend\src\app,frontend\src\test,infra,scripts | Out-Null`
- [ ] Scaffold backend dependencies and a `/api/health` route that returns `{"status":"ok"}`.
- [ ] Scaffold the frontend shell with the six tab labels from the spec and an empty-state layout.
- [ ] Verification:
  - `python -m venv .venv`
  - `.\.venv\Scripts\Activate.ps1`
  - `python -m pip install -e .\backend[dev]`
  - `npm install --prefix frontend`
  - `python -m pytest backend/tests/unit/test_health.py -q`
  - `npm --prefix frontend run test -- src/test/app-shell.test.tsx`
- [ ] Defer Compose boot checks until Task 2 defines runnable service images and container commands for `postgres` and `backend`.
- [ ] Commit: `git add .; git commit -m "chore: scaffold backend and frontend foundations"`

### Task 2: Add persistence, configuration, and secret abstractions

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/20260425_01_core_schema.py`
- Create: `backend/app/core/config.py`, `backend/app/core/db.py`, `backend/app/core/secrets.py`
- Create: `backend/app/models/base.py`, `backend/app/models/source.py`, `backend/app/models/setting.py`, `backend/app/models/technical_event.py`
- Create: `backend/tests/unit/test_config.py`, `backend/tests/unit/test_secret_store.py`, `backend/tests/unit/test_db_session.py`
- Create: `scripts/load-dev-secrets.ps1`
- Modify: `docker-compose.yml`, `.env.example`, `scripts/bootstrap.ps1`, `README.md`

- [ ] Implement `Settings` loading for non-secret values from environment and a `SecretStore` interface for the application master key and PostgreSQL password.
- [ ] Add a Windows Credential Manager implementation behind `backend/app/core/secrets.py` plus an in-memory test double for automated tests. Use exact secret names `good-news/dev/app-master-key` and `good-news/dev/postgres-password`.
- [ ] Add `scripts/load-dev-secrets.ps1` as the runtime contract for secret injection: the script reads those exact Windows Credential Manager entries and exports process-scoped PowerShell environment variables for the current shell session only, including `GOOD_NEWS_APP_MASTER_KEY`, `GOOD_NEWS_POSTGRES_PASSWORD`, and `POSTGRES_PASSWORD`, so host-side `python -m alembic -c backend/alembic.ini upgrade head` and `docker compose ...` both consume secrets without storing them in the repo.
- [ ] Update `scripts/bootstrap.ps1` and `README.md` so a fresh workspace can create or refresh those exact Windows Credential Manager entries before any migration or container boot, document the required dot-source flow `. .\scripts\load-dev-secrets.ps1`, and provide a non-secret verification step that prints whether each required secret is present and whether the three process-scoped environment variables are loaded in the current shell.
- [ ] Add SQLAlchemy base/session wiring and the first migration for `sources`, `settings`, `secret_settings`, and `technical_events`.
- [ ] Add runnable `postgres` and `backend` service definitions to `docker-compose.yml`, including the backend container command and the PostgreSQL dependency wiring used by later slices.
- [ ] Verification:
  - `.\scripts\bootstrap.ps1`
  - `. .\scripts\load-dev-secrets.ps1`
  - `.\scripts\bootstrap.ps1 -CheckSecrets`
  - `python -m pytest backend/tests/unit/test_config.py backend/tests/unit/test_secret_store.py backend/tests/unit/test_db_session.py -q`
  - `docker compose up -d postgres`
  - `python -m alembic -c backend/alembic.ini upgrade head`
  - `docker compose up -d backend`
- [ ] Commit: `git add .; git commit -m "feat: add config, secrets, and core database schema"`

### Task 3: Implement source onboarding, readaptation, and the Sources screen

**Files:**
- Create: `backend/app/schemas/source.py`, `backend/app/api/routes/sources.py`
- Create: `backend/app/parsing/discovery.py`, `backend/app/parsing/html_strategy.py`
- Create: `backend/app/services/source_onboarding.py`, `backend/app/services/source_readaptation.py`
- Create: `backend/tests/unit/test_source_discovery.py`, `backend/tests/unit/test_source_readaptation.py`, `backend/tests/api/test_sources_api.py`
- Create: `frontend/src/lib/api.ts`, `frontend/src/components/SourceForm.tsx`, `frontend/src/pages/SourcesPage.tsx`, `frontend/src/test/sources-page.test.tsx`
- Modify: `frontend/src/app/AppShell.tsx`, `docker-compose.yml`

- [ ] Implement deterministic source discovery first: normalized URL handling, common RSS/Atom paths, `link rel="alternate"` parsing, and sitemap/common-engine hints.
- [ ] Add HTML fallback strategy creation for sources without usable feeds; AI may help derive repeatable extraction hints or candidate selectors, but persist only deterministic rules or selectors that can be rerun without the model.
- [ ] Add `source_readaptation.py` that reruns the same onboarding flow for an existing failing source, marks `needs_readaptation` with a reason before retry, emits `technical_events` when onboarding or rediscovery leaves the source in a readaptation-needed or failed state, and only replaces the persisted strategy after a successful rediscovery.
- [ ] Expose `POST /api/sources`, `GET /api/sources`, and `PATCH /api/sources/{id}` so source state can be updated explicitly; cover create/list/toggle flows plus readaptation-needed responses in `backend/tests/api/test_sources_api.py`, including `active`, status, feed URL, strategy kind, last success, last failure, `needs_readaptation`, and `readaptation_reason`.
- [ ] Add the `frontend` service to `docker-compose.yml` before any frontend Compose verification: map the Vite port, wire it to reach the backend API container, and declare the dependency on `backend` so `docker compose up -d --build backend frontend` is actionable in a greenfield repo.
- [ ] Build the `Sources` page so the user can add a plain URL, toggle `active` on existing sources through the PATCH endpoint, and explicitly see source status, last successful sync time, plus `needs_readaptation` indication and reason; cover those UI states in `frontend/src/test/sources-page.test.tsx`.
- [ ] Verification:
  - `python -m pytest backend/tests/unit/test_source_discovery.py backend/tests/unit/test_source_readaptation.py backend/tests/api/test_sources_api.py -q`
  - `npm --prefix frontend run test -- src/test/sources-page.test.tsx`
  - `docker compose up -d --build backend frontend`
- [ ] Commit: `git add .; git commit -m "feat: add source onboarding workflow"`

### Task 4: Add scheduled ingestion, post storage, and the Feed screen

**Files:**
- Create: `backend/alembic/versions/20260425_02_posts_and_feedback.py`
- Create: `backend/app/models/post.py`, `backend/app/models/post_analysis.py`, `backend/app/models/feedback.py`, `backend/app/models/preference_profile.py`
- Create: `backend/app/services/source_sync.py`, `backend/app/jobs/scheduler.py`, `backend/app/jobs/source_jobs.py`
- Create: `backend/app/api/routes/posts.py`
- Create: `backend/tests/unit/test_source_sync.py`, `backend/tests/api/test_posts_api.py`
- Create: `frontend/src/components/PostCard.tsx`, `frontend/src/pages/FeedPage.tsx`, `frontend/src/test/feed-page.test.tsx`

- [ ] Persist discovered posts with canonical URL, title, published timestamp, raw excerpt or content, content hash, and ingest metadata.
- [ ] Add APScheduler startup wiring so active sources are polled on a fixed interval and inactive sources are skipped, and expose a one-shot `python -m app.jobs.source_jobs --run-once` entrypoint for deterministic local verification.
- [ ] Deduplicate posts by canonical URL first and content hash second, and update source success or failure timestamps plus readaptation flags on repeated failures.
- [ ] Trigger readaptation from the sync path after the configured failure threshold, emit `technical_events` for repeated-failure, readaptation-needed, and readaptation-failed outcomes, cover those paths in `backend/tests/unit/test_source_sync.py`, persist the updated strategy on success, and keep the old strategy plus failure metadata when readaptation still fails.
- [ ] Expose `GET /api/posts` with default ranking order placeholder, source filter, feedback-state filter, and a default "last month" window plus the explicit full-history contract `window=all`; cover both the default window and `window=all` in `backend/tests/api/test_posts_api.py`.
- [ ] Build the `Feed` page with post cards, original-link CTA, source filter, feedback-state filter, and a clear control labeled `All collected posts` that calls the same API with `window=all`; cover that control and request path in `frontend/src/test/feed-page.test.tsx`.
- [ ] Verification:
  - `python -m pytest backend/tests/unit/test_source_sync.py backend/tests/api/test_posts_api.py -q`
  - `python -m pytest backend/tests/unit/test_source_readaptation.py -q`
  - `npm --prefix frontend run test -- src/test/feed-page.test.tsx`
  - `docker compose up -d --build backend frontend postgres`
- [ ] Commit: `git add .; git commit -m "feat: add ingestion pipeline and feed page"`

### Task 5: Add local AI analysis, hybrid ranking, and the Preference Profile screen

**Files:**
- Create: `backend/app/ai/ollama_client.py`
- Create: `backend/app/services/analysis.py`, `backend/app/services/ranking.py`, `backend/app/services/preferences.py`
- Create: `backend/app/api/routes/preferences.py`
- Create: `scripts/pull-ollama-model.ps1`
- Create: `backend/tests/unit/test_analysis_service.py`, `backend/tests/unit/test_ranking.py`, `backend/tests/api/test_preferences_api.py`
- Create: `frontend/src/components/PreferenceSummary.tsx`, `frontend/src/pages/PreferenceProfilePage.tsx`, `frontend/src/test/preference-profile.test.tsx`
- Modify: `frontend/src/pages/FeedPage.tsx`, `backend/app/api/routes/posts.py`, `docker-compose.yml`, `.env.example`, `README.md`

- [ ] Add `scripts/pull-ollama-model.ps1` to fetch the exact Ollama model used by `analysis.py` and document the model name in `README.md` or `.env.example`.
- [ ] Define the `ollama` Compose service in `docker-compose.yml`, including its port or network exposure, persistent model storage, backend dependency wiring, and the backend environment values used by `ollama_client.py` to reach the containerized model runtime.
- [ ] Make model bootstrap expectations explicit: run `.\scripts\pull-ollama-model.ps1` against the `ollama` service before backend verification that depends on AI analysis, and document that verification assumes the named model is already present locally.
- [ ] Add Ollama-backed post analysis that generates a Russian summary, extracted topics, detected format, technical depth, verdict, and verdict reason.
- [ ] Implement inspectable ranking logic that combines explicit feedback, source affinity, topic affinity, format, practical engineering orientation, technical depth, and recency.
- [ ] Store aggregated preference-profile explanations so the UI can explain both positive and negative tendencies without exposing raw secrets or opaque model state.
- [ ] Update the feed API and page to show AI summary, verdict, verdict reason, and ranking-based ordering.
- [ ] Build the `Preference Profile` page from stored aggregate explanations.
- [ ] Verification:
  - `python -m pytest backend/tests/unit/test_analysis_service.py backend/tests/unit/test_ranking.py backend/tests/api/test_preferences_api.py -q`
  - `docker compose up -d ollama`
  - `.\scripts\pull-ollama-model.ps1`
  - `npm --prefix frontend run test -- src/test/preference-profile.test.tsx`
  - `docker compose up -d backend`
- [ ] Commit: `git add .; git commit -m "feat: add analysis, ranking, and preference profile"`

### Task 6: Add SMTP settings, daily digests, and email feedback actions

**Files:**
- Create: `backend/alembic/versions/20260425_03_digests.py`
- Create: `backend/app/models/digest.py`, `backend/app/models/digest_item.py`
- Create: `backend/app/services/settings_service.py`, `backend/app/services/digest_service.py`, `backend/app/services/email_service.py`
- Create: `backend/app/api/routes/settings.py`, `backend/app/api/routes/feedback.py`
- Create: `backend/app/jobs/digest_jobs.py`
- Create: `backend/app/email/templates/daily_digest.html.jinja2`
- Create: `backend/tests/unit/test_digest_service.py`, `backend/tests/unit/test_digest_email_template.py`, `backend/tests/unit/test_email_service.py`, `backend/tests/integration/test_daily_digest_job.py`, `backend/tests/api/test_settings_api.py`, `backend/tests/api/test_feedback_api.py`
- Create: `frontend/src/components/SettingsForm.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/test/settings-page.test.tsx`
- Modify: `backend/app/jobs/scheduler.py`

- [ ] Implement settings CRUD for daily digest time, recipient email, sender identity, SMTP host, SMTP port, SMTP username, security mode, and catch-up flags.
- [ ] Set the default daily digest schedule to `12:00` local time, validate the daily time field at the API layer, persist it in `settings`, and surface validation errors in the UI.
- [ ] Enforce write-only password handling: accept plaintext password on write, encrypt it before persistence, never return it from API responses, and expose only a configured or not-configured state.
- [ ] Add `POST /api/settings/test-email` backed by `email_service.py`, with fake SMTP transport coverage for both successful delivery and transport failure.
- [ ] Register the daily digest APScheduler job in `digest_jobs.py`, use the persisted daily schedule default on startup, reload only the daily digest trigger when settings change in this task, and run startup catch-up for the latest missed daily digest without backfilling more than one missed daily run.
- [ ] Generate a daily digest email that considers every post in the window, sends the top 5 ranked posts, and adds the exact remainder line `more X less interesting posts` when applicable.
- [ ] Require each digest item in the HTML output to include post title, source name, original link, Russian summary, verdict, verdict reason, and the three feedback links.
- [ ] Add direct feedback links for `interesting`, `not_interesting`, and `want_to_read` that persist feedback immediately and redirect to exact local targets: `interesting` and `not_interesting` return to `/feed`, while `want_to_read` returns to `/want-to-read`; cover the redirect target plus saved feedback in `backend/tests/api/test_feedback_api.py` or `backend/tests/integration/test_daily_digest_job.py`.
- [ ] Add the `Settings` page with daily schedule controls, SMTP test-email action, and masked password replacement flow.
- [ ] Verification:
  - `python -m pytest backend/tests/unit/test_digest_service.py backend/tests/unit/test_digest_email_template.py backend/tests/unit/test_email_service.py backend/tests/api/test_settings_api.py backend/tests/api/test_feedback_api.py backend/tests/integration/test_daily_digest_job.py -q`
  - `python -m pytest backend/tests/integration/test_daily_digest_job.py -q -k startup`
  - `npm --prefix frontend run test -- src/test/settings-page.test.tsx`
  - `python -m pytest backend/tests/api/test_settings_api.py -q -k "daily or test_email"`
  - `docker compose up -d --build backend frontend postgres`
- [ ] Commit: `git add .; git commit -m "feat: add smtp settings and daily digest delivery"`

### Task 7: Add weekly digest scheduling, catch-up, digest history, and the Want To Read screen

**Files:**
- Create: `backend/app/api/routes/digests.py`
- Create: `backend/tests/unit/test_digest_jobs.py`, `backend/tests/api/test_digests_api.py`
- Create: `frontend/src/components/DigestHistoryTable.tsx`, `frontend/src/pages/DigestsPage.tsx`, `frontend/src/pages/WantToReadPage.tsx`
- Create: `frontend/src/test/digests-page.test.tsx`, `frontend/src/test/want-to-read-page.test.tsx`
- Modify: `backend/app/jobs/scheduler.py`, `backend/app/api/routes/posts.py`, `backend/app/api/routes/settings.py`, `backend/tests/api/test_settings_api.py`, `frontend/src/components/SettingsForm.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/test/settings-page.test.tsx`

- [ ] Extend settings CRUD and the `Settings` page with weekly digest day and time controls, default them to `Saturday 23:30` local time on a fresh database, validate the fields at the API layer, and cover the weekly settings flow in `backend/tests/api/test_settings_api.py` plus `frontend/src/test/settings-page.test.tsx`.
- [ ] Add the weekly digest job, persisted digest history, and HTML web-version storage for sent digests.
- [ ] Wire APScheduler to use the persisted weekly day and time settings and reload the weekly digest trigger after settings changes.
- [ ] Implement startup catch-up logic for the latest missed weekly digest only, without backfilling more than one missed weekly run, because daily startup catch-up is already complete in Task 6.
- [ ] Expose digest-history API responses with sent time, digest type, included posts, and rendered HTML for browser viewing.
- [ ] Build the `Digests` and `Want To Read` pages from persisted data instead of client-only filtering.
- [ ] Verification:
  - `python -m pytest backend/tests/unit/test_digest_jobs.py backend/tests/api/test_digests_api.py -q`
  - `python -m pytest backend/tests/api/test_settings_api.py -q -k weekly`
  - `python -m pytest backend/tests/unit/test_digest_jobs.py -q -k weekly`
  - `npm --prefix frontend run test -- src/test/settings-page.test.tsx src/test/digests-page.test.tsx src/test/want-to-read-page.test.tsx`
  - `docker compose up -d --build backend frontend postgres`
- [ ] Commit: `git add .; git commit -m "feat: add digest history and catch-up behavior"`

### Task 8: Add observability, alerts, and the evening operations email

**Files:**
- Create: `infra/prometheus/prometheus.yml`
- Create: `infra/loki/config.yml`
- Create: `infra/otel/otel-collector-config.yaml`
- Create: `infra/grafana/provisioning/datasources/datasource.yml`
- Create: `infra/grafana/provisioning/dashboards/dashboards.yml`
- Create: `infra/grafana/dashboards/good-news-overview.json`
- Create: `infra/grafana/alerts/good-news-alerts.yml`
- Create: `backend/app/core/logging.py`, `backend/app/core/telemetry.py`, `backend/app/services/observability_report.py`
- Create: `backend/app/jobs/observability_jobs.py`, `backend/app/email/templates/observability_digest.html.jinja2`
- Create: `backend/tests/unit/test_observability_report.py`, `backend/tests/integration/test_observability_stack.py`, `backend/tests/integration/test_observability_email_job.py`
- Modify: `docker-compose.yml`, `README.md`

- [ ] Instrument the backend with structured logs, request and job metrics, and technical-event emission for source failures, digest failures, AI failures, email failures, Ollama outages, and database outages.
- [ ] Bring up Grafana, Prometheus, Loki, OpenTelemetry Collector, and grafana-image-renderer in `docker-compose.yml` and wire the backend to export logs and metrics into that stack.
- [ ] Add Grafana dashboards and alert rules for repeated source failures, digest send failure, observability report failure, Ollama unavailability, PostgreSQL unavailability, high parsing failure rate, and excessive AI processing failures.
- [ ] Register the daily evening observability report job in `observability_jobs.py`, set its default schedule to `18:00` local time in code, and wire scheduler startup so the job is present after app boot.
- [ ] Implement the evening observability email: Grafana screenshot for the previous 24 hours plus a text summary built from metrics, alerts, and `technical_events`.
- [ ] Persist each observability email run in `digests` with `digest_type = observability_daily`, the report time window, send status, send time, rendered HTML, and summary metadata even though it has no ranked post items.
- [ ] Update `README.md` with exact local-start commands, Windows Credential Manager secret names, and first-run steps for Ollama model pull plus migrations.
- [ ] Verification:
  - `python -m pytest backend/tests/unit/test_observability_report.py backend/tests/integration/test_observability_stack.py backend/tests/integration/test_observability_email_job.py -q`
  - `docker compose up -d --build`
  - `docker compose ps`
  - `Invoke-WebRequest http://localhost:8000/api/health`
  - `python -m pytest backend/tests/integration/test_observability_stack.py -q -k provisioning`
  - `python -m pytest backend/tests/integration/test_observability_email_job.py -q -k startup`
  - `Invoke-WebRequest "http://localhost:8081/render/d-solo/good-news-overview?from=now-24h&to=now&panelId=1" -OutFile .\observability.png`
  - `Test-Path .\observability.png`
- [ ] Verify the end-to-end observability email path by running the scheduled job with a fixed clock and fake SMTP transport, then assert one `observability_daily` row is stored and one rendered email with screenshot attachment is sent.
- [ ] Commit: `git add .; git commit -m "feat: add observability stack and operations email"`

## Final Acceptance Pass

- [ ] Run the full backend suite: `python -m pytest backend/tests -q`
- [ ] Run the full frontend suite: `npm --prefix frontend run test`
- [ ] Run the complete stack: `docker compose up -d --build`
- [ ] Smoke-check the user journey:
  - add a source in `Sources`
  - run `docker compose exec backend python -m app.jobs.source_jobs --run-once` to trigger one deterministic sync cycle against the configured active sources
  - confirm ingestion created posts in `Feed`
  - confirm summaries and verdicts are visible
  - mark one post `want_to_read`
  - run `python -m pytest backend/tests/integration/test_daily_digest_job.py -q` and confirm the fixed-clock scheduler verification creates one new digest record without a user-facing manual trigger
  - click an email feedback link and confirm redirect plus saved feedback
  - view digest history
  - open Grafana and confirm telemetry is flowing
- [ ] Commit the final stabilization pass: `git add .; git commit -m "chore: finish good news mvp phase 1"`
