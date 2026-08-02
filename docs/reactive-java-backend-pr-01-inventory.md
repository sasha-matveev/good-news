# PR-01 Backend Migration Inventory

This document freezes the current Python backend scope and contracts for PR-01 of the reactive Java backend migration. It is limited to repo facts that are present today, plus the minimum migration-planning classifications required to decide which current boundaries stay explicit and which ones are folded into the Java monolith.

## Scope guard

- Active backend entrypoint: `backend/app/main.py`.
- Active production backend topology: one FastAPI Cloud Run service, `good-news-app`, deployed by `.github/workflows/deploy.yml`.
- Database migrations remain Alembic-based today under `backend/alembic/` and are executed through the Cloud Run job `db-migrate`.
- Legacy split-service runtimes still exist in the repo under `backend/app/content_api_service/`, `backend/app/source_ingestion_service/`, `backend/app/analysis_llm_service/`, and `backend/app/delivery_service/`.
- This document does not define Java implementation details. It only freezes current scope, contracts, and migration classifications.

## Current `backend/app/` inventory

| Python area | Current repo contents | Current responsibility | Planned Java package area |
| --- | --- | --- | --- |
| `api/routes` | `health.py`, `posts.py`, `feedback.py`, `preferences.py`, `settings.py`, `sources.py`, `want_to_read.py`, `digests.py`, `monitoring.py`, `internal_jobs.py` | Public `/api/*` HTTP routes plus scheduler-triggered `/internal/jobs/*` routes mounted by `backend/app/main.py` | `web.api`, `web.internaljobs` |
| `schemas` | `post.py`, `feedback.py`, `preference.py`, `setting.py`, `source.py`, `want_to_read.py`, `digest.py` | Request and response DTOs for the current HTTP surface | `web.dto` |
| `models` | `source.py`, `post.py`, `post_analysis.py`, `feedback.py`, `read_later.py`, `digest.py`, `digest_item.py`, `preference_profile.py`, `setting.py`, `base.py` | SQLAlchemy persistence model for content, ranking feedback, settings, and digests | `persistence.model` |
| `services` | Listing, preferences, settings, digests, source onboarding/sync/readaptation, analysis, email, plus `*_service_client.py` and `*_boundary.py` adapters | Domain logic plus legacy HTTP client and boundary adapters | `application.posts`, `application.preferences`, `application.settings`, `application.sources`, `application.analysis`, `application.digests`, `application.delivery`, `integration.internal` |
| `jobs` | `analysis_jobs.py`, `digest_jobs.py`, `source_jobs.py` | Scheduled and batch orchestration for analysis, source sync, and digest/report dispatch | `jobs` |
| `core` | `backend_identity.py`, `config.py`, `db.py`, `migration_runner.py`, `request_auth.py`, `schema_guard.py`, `secrets.py` | Runtime config, DB bootstrap, migration runner, auth, response identity, and secret handling | `platform.config`, `platform.db`, `platform.auth`, `platform.secrets` |
| `ai` | `gemini_client.py` | Gemini API integration used by the active monolith and the legacy analysis runtime | `integration.gemini` |
| `parsing` | `discovery.py`, `html_strategy.py`, `known_sites.py`, `uber_engineering.py` | Source discovery, document loading, URL normalization, and site-specific parsing behavior used by ingestion flows | `application.sources.parsing` |

Planned Java package areas are a migration-planning grouping adopted by this document so the scope can be mapped before code moves start. The exact root package name is intentionally not fixed in PR-01 because no Java package naming exists in the repo yet.

## Active HTTP surface

`backend/app/main.py` mounts all public routers with the `/api` prefix and mounts `internal_jobs_router` without a prefix.

### Public API

| Method | Path | Current behavior |
| --- | --- | --- |
| `GET` | `/api/health` | Returns `{"status":"ok"}` when DB schema is current; returns HTTP 503 with `{"status":"error","reason":"database schema is not at head"}` when schema is behind. |
| `GET` | `/api/posts` | Lists posts with filters for `source_id`, `feedback_state`, `window`, `sort`, `limit`, `offset`, and `read_later`. |
| `POST` | `/api/posts/{post_id}/read-later` | Sets read-later state for a post and returns `{post_id, read_later}`. |
| `POST` | `/api/posts/{post_id}/open` | Verifies the post exists and returns `{"opened": true}`. |
| `PUT` | `/api/feedback/{post_id}` | Upserts a feedback state for a post. |
| `GET` | `/api/feedback/{post_id}/{state}` | Saves feedback from email links and redirects to frontend routes; `want_to_read` also persists a read-later row. |
| `GET` | `/api/preferences` | Recomputes the preference profile from current data and returns it. |
| `POST` | `/api/preferences/recompute` | Recomputes and persists the preference profile, then returns it. |
| `GET` | `/api/settings` | Returns current app settings. |
| `PUT` | `/api/settings` | Persists settings and re-registers digest scheduler jobs when an in-process scheduler exists. |
| `POST` | `/api/settings/test-email` | Sends a test email through the in-process delivery boundary in monolith mode; otherwise calls the legacy delivery HTTP service client. |
| `POST` | `/api/sources` | Creates a source and starts onboarding in monolith mode; otherwise delegates to the legacy ingestion HTTP service. |
| `GET` | `/api/sources/{source_id}/log` | Returns in-memory onboarding log lines plus completion status. |
| `GET` | `/api/sources` | Lists sources with post counts. |
| `PATCH` | `/api/sources/{source_id}` | Updates source active state. |
| `DELETE` | `/api/sources/{source_id}` | Deletes a source and cascades related content in application code. |
| `POST` | `/api/sources/{source_id}/sync` | Syncs one source in monolith mode only; legacy path returns HTTP 501. |
| `POST` | `/api/sources/{source_id}/reload-posts` | Deletes and reloads recent posts for one source in monolith mode only. |
| `POST` | `/api/sources/sync` | Runs one sync pass for all active sources, directly in monolith mode or via the legacy ingestion HTTP client. |
| `PUT` | `/api/want-to-read/{post_id}` | Sets or clears the `want_to_read` feedback state for a post. |
| `GET` | `/api/digests` | Lists sent digests. |
| `GET` | `/api/digests/{digest_id}` | Returns one sent digest or HTTP 404 if it is missing. |
| `GET` | `/api/monitoring/summary` | Returns aggregate counts and service health status. |
| `POST` | `/api/monitoring/analyze-now` | Drains one batch of pending analysis work when an analysis client is configured; otherwise returns HTTP 503. |
| `GET` | `/api/monitoring/queue` | Lists up to 100 posts that still lack a `PostAnalysis` row. |

### Internal job API

| Method | Path | Current behavior |
| --- | --- | --- |
| `POST` | `/internal/jobs/source-sync` | Requires Cloud Scheduler OIDC auth, runs source sync, then attempts pending post analysis. |
| `POST` | `/internal/jobs/digests` | Requires Cloud Scheduler OIDC auth and dispatches bundled digest/report behavior in one endpoint. |

`/internal/jobs/digests` currently bundles three behaviors in one call:

- Daily digest catch-up and send logic.
- Weekly digest catch-up and send logic.

## Legacy internal service contracts to freeze before migration

These contracts still exist in the repo even though the active production topology deploys one Cloud Run monolith. Repo fact: the active internal production HTTP surface is `/internal/jobs/*` from `backend/app/api/routes/internal_jobs.py`, not the legacy split-service contracts listed below. PR-01 therefore keeps these contracts in the inventory as repo facts, but only treats them as required Java migration scope when the current active production path actually depends on them.

| Current contract | Repo evidence | PR-01 scope classification | Grounding |
| --- | --- | --- | --- |
| `/internal/ingestion/onboarding-commands` | `backend/app/source_ingestion_service/main.py`, `backend/app/services/source_ingestion_service_client.py`, `backend/app/services/ingestion_boundary.py` | Legacy-present fallback contract; not required Java migration scope by default | `/api/sources` already executes onboarding directly in monolith mode. The HTTP contract remains in the repo as a legacy adapter path for the split ingestion runtime, not as the current active production path. |
| `/internal/ingestion/sync/run-once` | `backend/app/source_ingestion_service/main.py`, `backend/app/services/source_ingestion_service_client.py` | Legacy-present fallback contract; not required Java migration scope by default | The active production path runs sync directly in monolith mode from `/api/sources/sync` and `/internal/jobs/source-sync`. The HTTP contract remains as a legacy split-runtime path that still exists in the repo. |
| `/internal/analysis/requests` | `backend/app/analysis_llm_service/main.py`, `backend/app/services/analysis_service_client.py`, `backend/app/services/analysis.py` | Legacy-present split-runtime contract; not required Java migration scope by default. Optional to keep explicit only if a later migration plan chooses that seam (planning inference). | Repo fact: the active monolith wires `analysis_client_factory` to `GeminiClient` in `backend/app/main.py`, while `/internal/analysis/requests` is exposed by the separate legacy analysis runtime and called by `AnalysisServiceClient`. Planning inference: the seam can stay visible in inventory discussions, but repo presence alone does not make it required migration scope. |
| `/internal/delivery/test-email` | `backend/app/delivery_service/main.py`, `backend/app/services/delivery_service_client.py`, `backend/app/services/delivery_boundary.py` | Legacy-present fallback contract; not required Java migration scope by default | `/api/settings/test-email` already calls `send_test_email_command(...)` directly in monolith mode and only falls back to HTTP for the legacy split-service path. |
| `/internal/delivery/digests/run-once` | `backend/app/delivery_service/main.py`, `backend/app/services/delivery_service_client.py`, `backend/app/jobs/digest_jobs.py` | Legacy-present split-runtime contract; not required Java migration scope by default | Digest execution in the active production path already runs in-process through `/internal/jobs/digests` and `backend/app/jobs/digest_jobs.py`. This HTTP contract remains on the legacy delivery runtime in the repo. |
| `/internal/delivery/digests/catch-up/run-once` | `backend/app/delivery_service/main.py` | Legacy-present split-runtime contract; not required Java migration scope by default | Catch-up logic already lives in `backend/app/jobs/digest_jobs.py` and is triggered by the active `/internal/jobs/digests` path. The explicit HTTP endpoint exists only on the legacy delivery runtime. |

## Operational dependencies frozen from the current repo

| Dependency | Current repo fact |
| --- | --- |
| FastAPI on Cloud Run | `README.md` and `.github/workflows/deploy.yml` describe and deploy one FastAPI monolith to Cloud Run service `good-news-app`. |
| Alembic migrations | `.github/workflows/deploy.yml` deploys and executes Cloud Run job `db-migrate`; `backend/alembic/` and `backend/alembic.ini` are present. |
| Firebase Auth plus backend email allowlist | `backend/app/core/request_auth.py` enforces Firebase ID token validation and allowlisted verified emails on `/api/*`, exempting `/api/health` and `/internal/*`. |
| Gemini integration | `backend/app/ai/gemini_client.py` is used by `backend/app/main.py` and `backend/app/analysis_llm_service/main.py`; `backend/app/core/config.py` requires `GOOD_NEWS_GEMINI_API_KEY`. |
| Gmail SMTP digest delivery | `README.md` describes Gmail SMTP delivery; `backend/app/services/email_service.py` and digest jobs implement SMTP-based email sending from settings stored in the app DB. |
| Secret Manager secrets | `.github/workflows/deploy.yml` injects `good-news-db-url`, `good-news-app-master-key`, and `good-news-gemini-api-key` into Cloud Run. |
| Cloud Scheduler OIDC calls | `README.md`, `.github/workflows/deploy.yml`, and `backend/app/api/routes/internal_jobs.py` show Scheduler invoking `/internal/jobs/*` with Google OIDC tokens verified against the configured scheduler service account and audience. |

## Legacy split-service runtimes: collapse or preserve

Repo fact: these runtime directories still exist in the repo. Repo fact: `.github/workflows/deploy.yml` deploys `backend/app/main.py` as the active production backend and does not deploy these runtimes separately. PR-01 should therefore distinguish "present in repo" from "used in the current active production path" and should not automatically include a legacy runtime in Java migration scope just because the directory exists.

| Runtime directory | Current status in repo | PR-01 scope classification | Grounding |
| --- | --- | --- | --- |
| `backend/app/content_api_service/` | Legacy content API entrypoint still exists | Legacy-present runtime; not automatically required Java migration scope by default | The active production topology deploys `backend/app/main.py` as one Cloud Run service and no workflow step deploys a separate content API runtime. |
| `backend/app/source_ingestion_service/` | Legacy ingestion runtime still exists | Legacy-present runtime; not automatically required Java migration scope by default | The active app already contains direct in-process source onboarding and sync paths, and no separate ingestion deploy exists in the workflow. |
| `backend/app/delivery_service/` | Legacy delivery runtime still exists | Legacy-present runtime; not automatically required Java migration scope by default | Digest scheduling and delivery logic already run in-process through `/internal/jobs/digests` and app services in the active runtime. |
| `backend/app/analysis_llm_service/` | Legacy analysis runtime still exists | Legacy-present runtime; not automatically required Java migration scope by default. Optional to preserve as an explicit seam only if a later migration plan chooses that seam (planning inference). | Repo fact: the active deployment topology is one backend service, not a separately deployed analysis service. Planning inference: `/internal/analysis/requests` can remain explicit in inventory discussions because the repo still preserves that request/response seam and client, but the runtime is not active production scope by default. |

This is the narrowest repo-grounded conclusion available today: the split runtimes are present in the repo but are not the active production topology. PR-01 should therefore inventory them as legacy inputs and only pull them into required Java migration scope when the current active production path depends on them. In this document, the only explicitly preserved seam is `/internal/analysis/requests`, and that explicitness is labeled as a PR-01 planning inference rather than an active-runtime fact.

## Evidence pointers

- Entrypoints: `backend/app/main.py`, `backend/app/content_api_service/main.py`, `backend/app/source_ingestion_service/main.py`, `backend/app/analysis_llm_service/main.py`, `backend/app/delivery_service/main.py`
- Public routes: `backend/app/api/routes/*.py`
- Internal jobs: `backend/app/api/routes/internal_jobs.py`
- Domain and adapter services: `backend/app/services/*.py`
- Job orchestration: `backend/app/jobs/*.py`
- Runtime infrastructure: `backend/app/core/*.py`
- Deployment and operations: `README.md`, `.github/workflows/deploy.yml`
