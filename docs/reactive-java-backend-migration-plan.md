# Reactive Java Backend Migration Plan

## Principles and Constraints

- Target stack: Java 21, Spring Boot 3, WebFlux, Reactor, Maven, R2DBC, Flyway.
- Migration is incremental. The current FastAPI backend in `backend/` stays operational until Java takes over each contract.
- Each phase must fit in one GPT-5.4 mini session, end in one merged PR, and leave the repo in a working state.
- Runtime paths must stay fully reactive: WebFlux controllers, Reactor services, R2DBC persistence, WebClient for HTTP integrations. Do not introduce JPA or JDBC into request-processing code.
- Existing backend behavior is the source of truth at first: keep current API shapes, auth rules, DB semantics, scheduler entrypoints, and operational topology before attempting cleanup.
- Existing deployment model matters: production today is a FastAPI monolith on Cloud Run, migrations run through a Cloud Run job, CI is in `.github/workflows/ci.yml`, and deploy is in `.github/workflows/deploy.yml`. The repo still contains legacy split-service runtimes and tests such as `source_ingestion_service`, `analysis_llm_service`, `delivery_service`, and `content_api_service`; those traces must be inventoried explicitly instead of being mistaken for the active production topology.
- Keep the new backend in a separate module such as `backend-java/` until cutover is complete.
- During the parallel-run window, Python and Java must both be able to operate against the same source-of-truth database. Their DB schema expectations, persisted-data semantics, auth behavior, CORS/public-origin handling, and frontend-visible API contracts must remain compatible for as long as parallel operation exists.
- Frontend backend selection is a migration-time internal validation mechanism, not a permanent production end-user feature. It must switch all browser API requests between Python and Java without introducing page-specific request wiring.
- Cloud Run, Firebase Auth, Gemini, Gmail SMTP, Secret Manager, and Neon Postgres all need explicit migration steps. None of them should be treated as "will wire later".
- Blocking libraries may still exist at the edges, especially SMTP, HTML parsing, and some crypto operations. If blocking code cannot be avoided, isolate it explicitly away from the Netty event loop and document the scheduler choice in the PR.

## PR Phases

### PR-01. Freeze Migration Scope and Current Contracts [Completed on master]

**Goal**

Create a single source of truth for what the Java backend must replace.

**Status**

- Completed on `master`.
- Artifact: `docs/reactive-java-backend-pr-01-inventory.md`.
- Reviewed artifact source for this plan update: `C:\Users\ytype\dev\projects\good-news\docs\reactive-java-backend-pr-01-inventory.md`.

**Exact changes**

- Inventory the current Python backend structure in `backend/app/`:
  - `api/routes`
  - `schemas`
  - `models`
  - `services`
  - `jobs`
  - `core`
- Capture the current HTTP surface:
  - `/api/health`
  - `/api/posts`
  - `/api/feedback/*`
  - `/api/preferences*`
  - `/api/settings*`
  - `/api/sources*`
  - `/api/want-to-read*`
  - `/api/digests*`
  - `/api/monitoring*`
  - `/internal/jobs/source-sync`
  - `/internal/jobs/digests`
- Capture the legacy internal service contracts still present in the repo and classify each one as either "migrate as an in-process Java module, then retire the HTTP boundary" or "retain as an explicit Java internal contract" before any code move starts:
  - `/internal/ingestion/*`
  - `/internal/analysis/requests`
  - `/internal/delivery/*`
- For `/internal/jobs/digests`, explicitly inventory the currently bundled behaviors:
  - daily digests
  - weekly digests
  - daily observability report
- Capture operational dependencies from the current repo:
  - FastAPI on Cloud Run
  - Alembic migrations
  - Firebase Auth plus backend email allowlist
  - Gemini integration
  - Gmail SMTP digest delivery
  - Secret Manager secrets
  - Cloud Scheduler OIDC calls
- Add a migration inventory document that maps Python modules to planned Java packages.
- Record whether the legacy split-service runtimes under `backend/app/*_service/` are being collapsed into the new Java monolith or intentionally preserved for a reason.

**Definition of done**

- The team has an explicit inventory of all routes, domain areas, jobs, integrations, and runtime boundaries that must move.
- Nothing in later PRs depends on memory or verbal agreement.

**Verification**

- Compare the document against `backend/app/api/routes`, `backend/app/models`, `backend/app/services`, `backend/app/jobs`, `backend/app/core/config.py`, `README.md`, and `.github/workflows/*.yml`.

**Risks/notes**

- Skipping this phase is the fastest way to lose scheduler/auth/integration behavior during the rewrite.

### PR-02. Create the `backend-java` Maven Skeleton

**Goal**

Introduce a minimal Java backend module that builds and starts.

**Exact changes**

- Create `backend-java/` as a standalone Maven module.
- Add `pom.xml` with:
  - `spring-boot-starter-webflux`
  - `spring-boot-starter-validation`
  - `spring-boot-starter-actuator`
  - `spring-boot-starter-security`
  - `spring-boot-starter-data-r2dbc`
  - `r2dbc-postgresql`
  - `flyway-core`
  - `postgresql`
  - `spring-boot-starter-test`
  - `reactor-test`
  - `micrometer-registry-prometheus`
- Add the main `SpringBootApplication`.
- Add a smoke test that the Spring context loads.
- Add Java build output ignores if needed, without changing existing tracked app behavior.

**Definition of done**

- `backend-java` builds with Maven.
- The application starts locally with an empty skeleton.
- Unit test baseline is green.

**Verification**

- `mvn -f backend-java/pom.xml test`
- `mvn -f backend-java/pom.xml spring-boot:run` smoke start

**Risks/notes**

- Keep this PR boring. Do not add business logic yet.
- Merge PR-03 immediately after this phase and do not start Java feature work before the dedicated Java CI job exists.

### PR-03. Add GitHub CI for `backend-java`

**Goal**

Introduce first-class GitHub CI for the Java backend before feature migration begins.

**Exact changes**

- Extend `.github/workflows/ci.yml` or add a dedicated Java CI workflow for `backend-java`.
- Include:
  - Maven dependency resolution
  - unit tests
  - integration tests
  - lint or formatting check if adopted
  - caching strategy for Maven dependencies
- Make the workflow path-aware if that keeps PR feedback fast.
- Ensure Java CI can run alongside the existing Python and frontend jobs during the migration period.

**Definition of done**

- Pull requests touching `backend-java` automatically run Java CI in GitHub Actions.
- The Java backend is no longer relying only on local verification.

**Verification**

- Open a PR or branch push that triggers the workflow successfully.
- Confirm expected failures appear when a Java test is intentionally broken and then restored.

**Risks/notes**

- This phase is intentionally early so the per-PR rule about local and CI verification is enforceable for the rest of the Java migration backlog.

### PR-04. Port Configuration and Environment Contract

**Goal**

Reproduce the current backend config surface in Spring configuration classes.

**Exact changes**

- Read `backend/app/core/config.py` and map every active `GOOD_NEWS_*` setting into typed `@ConfigurationProperties`.
- Split configuration into logical groups:
  - app
  - database
  - auth
  - scheduler
  - gemini
  - email
  - observability
- Add validation annotations for required values in non-local environments.
- Create `application.yml` and a local override file pattern.
- Preserve compatibility with the existing secret names and env names used by Cloud Run and GitHub Actions deploys.

**Definition of done**

- Java can bind the same environment contract used by the Python service.
- Missing required configuration fails fast and predictably.

**Verification**

- Maven unit tests for property binding and validation failures.
- Manual startup with a local env file or shell env to prove binding.

**Risks/notes**

- Do not rename env vars during migration. Config churn here multiplies operational risk later.

### PR-05. Add Health, Actuator, and Observability Baseline

**Goal**

Stand up the minimum operational surface expected from the backend.

**Exact changes**

- Add `/api/health` with the same externally visible semantics as the FastAPI health route.
- Enable Spring Boot Actuator.
- Expose Prometheus metrics for future Cloud Run monitoring.
- Add request logging and correlation-id strategy if the Python app already emits equivalent observability markers.
- Document how Java metrics will coexist with the current service during migration.

**Definition of done**

- `/api/health` works from the Java service.
- Actuator and Prometheus endpoints are available for internal ops.

**Verification**

- Integration test for `/api/health`.
- Manual check of actuator metrics endpoint.

**Risks/notes**

- Do not replace the current public health contract with a default actuator payload if existing consumers depend on the current route.

### PR-06. Establish Reactive Postgres Connectivity

**Goal**

Connect Java to Postgres the reactive way before any domain migration.

**Exact changes**

- Configure R2DBC PostgreSQL connection settings.
- Add shared DB configuration classes using `DatabaseClient` and/or `R2dbcEntityTemplate`.
- Add a small connectivity or repository smoke path.
- Set up Testcontainers PostgreSQL for integration testing.

**Definition of done**

- The Java service can connect to Postgres reactively.
- Integration tests can boot against an isolated PostgreSQL container.

**Verification**

- Maven integration test against Testcontainers.
- Manual startup against a dev DB branch if available.

**Risks/notes**

- Reject any shortcut that introduces JPA entities or JDBC repositories into runtime code.

### PR-07. Port Core Content Schema to Flyway

**Goal**

Start Flyway migration parity with the smallest high-value table group.

**Exact changes**

- Translate only the core content-related Alembic schema into ordered Flyway migrations under `backend-java/src/main/resources/db/migration/`.
- Preserve tables and relationships used by:
  - sources
  - posts
  - feedback
  - preference profiles
- Document any Alembic behavior that does not translate one-to-one and how it is handled.

**Definition of done**

- A clean database can be created with the core content tables needed by the first user-facing read and feedback routes.

**Verification**

- Testcontainers migration test on an empty DB.
- Schema assertion tests for sources, posts, feedback, and preference-related tables.

**Risks/notes**

- Avoid trying to "improve" the schema during the port. Stack migration and schema redesign together is a bad trade.

### PR-08. Port Settings and Read-Later Schema to Flyway

**Goal**

Add the user-settings tables needed for later settings and want-to-read migration work.

**Exact changes**

- Translate the Alembic schema for:
  - settings
  - read later
- Preserve keys, nullability, defaults, and any uniqueness rules currently relied on by the Python service.

**Definition of done**

- A clean database can be created with settings and read-later tables on top of the core content schema from PR-07.

**Verification**

- Testcontainers migration test on an empty DB.
- Schema assertion tests for settings and read-later tables.

**Risks/notes**

- Keep this separate from digest and analysis tables so the PR stays reviewable and executable in one session.

### PR-09. Port Digest and Analysis Schema to Flyway

**Goal**

Finish schema parity for the remaining digest and analysis features without bundling unrelated route work.

**Exact changes**

- Translate the Alembic schema for:
  - digests
  - digest items
  - post analysis
- Preserve foreign keys and any retention/history assumptions currently visible to the Python backend and UI.

**Definition of done**

- A clean database can be created with digest and analysis tables on top of the earlier Flyway phases.

**Verification**

- Testcontainers migration test on an empty DB.
- Schema assertion tests for digest, digest item, and post-analysis tables.

**Risks/notes**

- This split is intentional: one mega-schema PR is too large for the one-session, one-PR rule.

### PR-10. Build Reactive Security Foundation

**Goal**

Reproduce the current auth and invoker model in WebFlux.

**Exact changes**

- Read `backend/app/core/request_auth.py` and port the auth flow into Spring Security WebFlux.
- Support Firebase token verification and backend email allowlist behavior.
- Support the Cloud Scheduler OIDC invoker checks used for `/internal/jobs/*`.
- Declare which endpoints remain public and which require user auth or scheduler auth.

**Definition of done**

- User-authenticated routes, public routes, and internal-job routes follow the same access rules as the Python backend.

**Verification**

- Security integration tests for:
  - public health access
  - authenticated user access
  - rejected user token
  - rejected allowlist email
  - accepted scheduler invoker
  - rejected scheduler invoker

**Risks/notes**

- This needs to come early. Retrofitting auth after controllers are built creates repeated rework.

### PR-11. Define User-Facing DTO Contract

**Goal**

Port only the first wave of user-facing request and response shapes needed by the early API moves.

**Exact changes**

- Port the active Pydantic request and response shapes from `backend/app/schemas/` into Java DTOs for:
  - posts
  - feedback
  - preferences
  - settings
  - want to read
- Add validation annotations to mirror existing FastAPI validation for those route groups.

**Definition of done**

- DTOs exist for the earliest user-facing route groups and are ready to support PR-14 through PR-21.

**Verification**

- Serialization tests for the DTOs above.
- Validation tests for representative valid and invalid payloads.

**Risks/notes**

- Keep this phase narrow. The goal is to unblock early routes, not to port every schema at once.

### PR-12. Define Sources, Digests, Monitoring, and Internal DTO Contract

**Goal**

Port the remaining DTO surface that supports source management, digests, monitoring, and internal-job entrypoints.

**Exact changes**

- Port the active Pydantic request and response shapes into Java DTOs for:
  - sources
  - digests
  - monitoring
  - internal job payloads or response wrappers that are part of the current contract
- Add validation annotations to mirror existing FastAPI validation for those route groups.

**Definition of done**

- DTOs exist for the remaining route groups that are not covered by PR-11.

**Verification**

- Serialization tests.
- Validation tests.

**Risks/notes**

- Keep legacy internal-service contract DTO decisions explicit here if any of those HTTP boundaries are temporarily retained.

### PR-13. Define Shared Error and Validation Contract

**Goal**

Centralize error and validation behavior after the DTO surface has been split into manageable phases.

**Exact changes**

- Add global exception mapping for the expected HTTP status patterns.
- Document deliberately preserved quirks in current API behavior.
- Ensure validation failures for DTOs from PR-11 and PR-12 match current backend expectations closely enough for the frontend and internal callers.

**Definition of done**

- Error handling is centralized and consistent with the current backend contract.

**Verification**

- Exception handler integration tests.
- Validation failure contract tests.

**Risks/notes**

- "Cleaner" Spring errors are not the goal yet. Contract compatibility is.

### PR-14. Port `/api/posts` Read Path

**Goal**

Move the main feed listing endpoint into Java with reactive data access.

**Exact changes**

- Read `backend/app/api/routes/posts.py` and `backend/app/services/post_listing.py`.
- Implement reactive query logic for the posts feed.
- Preserve sorting semantics such as "By match" and "By date".
- Preserve any filtering, pagination, and enrichment currently returned to the React frontend.

**Definition of done**

- The Java `/api/posts` endpoint returns compatible feed responses for the current UI.

**Verification**

- Integration tests seeded from a test database.
- Contract comparison against the Python route for representative scenarios.

**Risks/notes**

- Ranking and date ordering are user-visible. Small mismatches will show up quickly.

### PR-15. Port Want-to-Read Endpoints

**Goal**

Move the saved-for-later feature into Java.

**Exact changes**

- Read `backend/app/api/routes/want_to_read.py` and `backend/app/services/read_later_service.py`.
- Port read/write behavior for read-later state.
- Preserve idempotency and existing response semantics.

**Definition of done**

- Save-for-later flows work through Java and match the current frontend expectations.

**Verification**

- Integration tests for add, remove, list, and repeat operations.

**Risks/notes**

- This path is a good early write test because it is narrower than settings or source sync.

### PR-16. Port Feedback Endpoints

**Goal**

Move explicit post feedback handling into Java.

**Exact changes**

- Read `backend/app/api/routes/feedback.py` and related services/models.
- Port feedback read and write behavior.
- Preserve all accepted feedback states and transitions.

**Definition of done**

- Feedback can be created, updated, and read through Java without UI changes.

**Verification**

- API integration tests for each feedback state.
- Contract comparison with Python for representative payloads.

**Risks/notes**

- Feedback influences downstream preference and ranking logic, so state semantics must remain stable.

### PR-17. Port Preferences Read API

**Goal**

Move preference profile retrieval into Java.

**Exact changes**

- Read `backend/app/api/routes/preferences.py` and `backend/app/services/preferences.py`.
- Port the read-only preference profile endpoint first.
- Preserve the shape used by the Preferences tab, including empty-state behavior.

**Definition of done**

- The Preferences UI can fetch profile data from Java.

**Verification**

- Integration tests with seeded preference records and empty-profile cases.

**Risks/notes**

- Do not conflate "no profile yet" with a hard error if Python currently treats it differently.

### PR-18. Port Preferences Recompute Flow

**Goal**

Move preference recalculation into Java.

**Exact changes**

- Port the recompute endpoint and its service orchestration.
- Preserve the current dependency chain between posts, feedback, and preference output.
- Keep the implementation fully reactive end to end.

**Definition of done**

- Preference recomputation works in Java and updates the same persisted state expected by the UI.

**Verification**

- Integration tests for recompute with controlled source data.
- Tests proving no `.block()` calls are used in the service path.

**Risks/notes**

- This is the first place where reactive composition discipline really matters.

### PR-19. Port Settings Read and Update API

**Goal**

Move digest and SMTP settings management into Java.

**Exact changes**

- Read `backend/app/api/routes/settings.py` and `backend/app/services/settings_service.py`.
- Port settings retrieval and update flows.
- Preserve validation and persistence semantics for delivery schedule, sender settings, and related fields.

**Definition of done**

- The Settings tab can read and save settings through Java.

**Verification**

- API integration tests for valid and invalid updates.

**Risks/notes**

- This PR must preserve the contract for later SMTP and digest-delivery steps.

### PR-20. Port Secret Handling and SMTP Credential Compatibility

**Goal**

Ensure Java can read and write the same encrypted SMTP credential data used today.

**Exact changes**

- Read `backend/app/core/secrets.py` and the settings/email service code paths.
- Port app master key handling and SMTP password encryption/decryption behavior.
- Prove compatibility with already stored DB values or document a safe migration if exact compatibility is impossible.

**Definition of done**

- Existing encrypted SMTP settings remain usable after Java takes over.

**Verification**

- Unit tests using fixed vectors from the current Python implementation.
- Cross-language compatibility checks where possible.

**Risks/notes**

- This is a high-risk compatibility step. A mismatch here breaks delivery for existing users.

### PR-21. Port Test Email Flow

**Goal**

Move the Settings "send test email" action into Java.

**Exact changes**

- Read `backend/app/services/email_service.py` and any settings test-email route handling.
- Implement SMTP send logic behind a dedicated adapter.
- Explicitly isolate blocking SMTP client work away from the Netty event loop.

**Definition of done**

- The Java backend can send the same test email flow used by the Settings UI.

**Verification**

- Adapter tests.
- Integration-like tests against a mock SMTP server.

**Risks/notes**

- Treat SMTP as a controlled blocking boundary rather than pretending it is natively reactive.

### PR-22. Port Digest History Read API

**Goal**

Move digest history viewing into Java.

**Exact changes**

- Read `backend/app/api/routes/digests.py` and `backend/app/services/digest_history.py`.
- Port digest list and digest detail read behavior.
- Preserve ordering, payload shape, and nested digest item behavior.

**Definition of done**

- Digest screens can read history from Java without frontend changes.

**Verification**

- Integration tests for digest list and detail endpoints.

**Risks/notes**

- Nested response structures make this a good place for contract tests, not just happy-path assertions.

### PR-23. Port Sources Read API

**Goal**

Move read-only source management views into Java.

**Exact changes**

- Read `backend/app/api/routes/sources.py`.
- Port source listing and source log/detail reads first.
- Preserve whatever source status data and audit fields the frontend already expects.

**Definition of done**

- The Sources UI can list sources and inspect source state via Java.

**Verification**

- Integration tests with seeded source records.

**Risks/notes**

- Splitting read from write keeps the PR manageable and reduces sync-risk early.

### PR-24. Port Sources CRUD

**Goal**

Move source creation, update, and delete flows into Java.

**Exact changes**

- Port source create, edit, enable/disable, and delete behavior.
- Preserve current validations around URLs, duplicates, and source state transitions.
- Keep response shapes aligned with the existing frontend.

**Definition of done**

- Source management in the UI can write through Java.

**Verification**

- API integration tests covering create/update/delete and duplicate URL handling.

**Risks/notes**

- Avoid combining CRUD with sync in the same PR. They touch different failure modes.

### PR-25. Create Shared Reactive External HTTP Client Layer

**Goal**

Standardize outbound HTTP before moving Gemini and source ingestion integrations.

**Exact changes**

- Add a shared WebClient configuration layer.
- Define retry, timeout, error mapping, and logging policies.
- Add client test utilities for mocked external services.

**Definition of done**

- All later outbound HTTP integrations can build on one shared reactive client foundation.

**Verification**

- Unit tests for retry and error translation behavior.

**Risks/notes**

- Do not duplicate raw WebClient setup across multiple services.

### PR-26. Port Source Discovery and Parsing Foundation

**Goal**

Move reusable ingestion groundwork before full source-sync orchestration.

**Exact changes**

- Read `backend/app/parsing/discovery.py`, `known_sites.py`, `html_strategy.py`, and related parsing helpers.
- Port source discovery and parsing utilities.
- Preserve known-site adaptations such as Uber Engineering parsing behavior where still relevant.
- Explicitly isolate parsing work if it is CPU-heavy or blocking.

**Definition of done**

- Java can fetch and parse representative source content at the helper/service level.

**Verification**

- Unit tests using the same or equivalent parsing fixtures as the Python backend.

**Risks/notes**

- Parsing code is a common place to accidentally block event-loop threads.

### PR-27. Port Single-Source Sync

**Goal**

Move the simplest end-to-end ingestion path into Java.

**Exact changes**

- Read `backend/app/services/source_sync.py`, `source_onboarding.py`, and `ingestion_boundary.py`.
- Port single-source sync flow: fetch, parse, deduplicate, persist posts, update source state.
- Reproduce the current single-source sync route behavior from the Sources UI or admin path.

**Definition of done**

- One source can be synced end to end by the Java backend with results written to Postgres.

**Verification**

- Integration tests with fixture feeds.
- Tests for duplicate post handling and source status updates.

**Risks/notes**

- Keep concurrency simple in this phase. Bulk orchestration comes later.

### PR-28. Port Bulk Source Sync

**Goal**

Move the batch ingestion workflow into Java.

**Exact changes**

- Port the route or service path that syncs all eligible sources.
- Add explicit concurrency limits and failure aggregation.
- Preserve monitoring-relevant outcome data where the current backend exposes it.

**Definition of done**

- Java can perform bulk source sync safely and predictably.

**Verification**

- Integration tests for multiple sources.
- Stress-style tests for concurrency caps and partial failures.

**Risks/notes**

- This PR must not create unbounded parallelism. Reactive does not mean unlimited concurrency.

### PR-29. Port Reload/Refresh Source Post Flows

**Goal**

Move the specialized source refresh paths that go beyond normal sync.

**Exact changes**

- Port any dedicated reload-posts or rescan logic used by the Python backend.
- Preserve semantics around re-fetching, replacing, or re-evaluating source content.

**Definition of done**

- Special source reload flows work in Java and match current admin/user expectations.

**Verification**

- Integration tests for reload behavior and duplicate-safe updates.

**Risks/notes**

- This logic is easy to get subtly wrong because it mixes ingestion and reconciliation.

### PR-30. Port Analysis Domain Flow Without LLM

**Goal**

Move the orchestration around analysis before wiring the real Gemini client.

**Exact changes**

- Read `backend/app/services/analysis.py`, `analysis_service_client.py`, and related models.
- Port analysis service orchestration and persistence of analysis results.
- Keep the client behind an abstraction so the LLM transport is not mixed into domain logic.

**Definition of done**

- Java can run the non-transport parts of the analysis pipeline.

**Verification**

- Unit tests for analysis orchestration and result persistence mapping.

**Risks/notes**

- This separation will make the Gemini port much easier to test and review.

### PR-31. Port Gemini Reactive Client

**Goal**

Move the LLM transport layer into Java.

**Exact changes**

- Read `backend/app/ai/gemini_client.py`.
- Implement a Gemini client using WebClient.
- Preserve model selection, request shaping, retry policy, and stub/test behavior used today.
- Add response parsing and error translation that match current service expectations.

**Definition of done**

- Java can call Gemini for analysis and can run in a stubbed mode where the Python backend currently supports it.

**Verification**

- Mocked HTTP client tests.
- Service integration tests for success, retryable failure, and permanent failure cases.

**Risks/notes**

- Rate limiting and retries need explicit design. Naive retries can amplify cost and latency.

### PR-32. Port Monitoring API

**Goal**

Move monitoring and queue visibility endpoints into Java.

**Exact changes**

- Read `backend/app/api/routes/monitoring.py` and `backend/app/services/observability_report_service.py`.
- Port monitoring summary, queue, and analyze-now behaviors.
- Preserve the UI-facing operational summaries currently shown in the Monitoring tab.

**Definition of done**

- Monitoring routes serve compatible data from Java.

**Verification**

- API integration tests for summary and queue views.
- Tests for analyze-now request handling if present.

**Risks/notes**

- Monitoring endpoints often accumulate special-case logic. Port the behavior before attempting cleanup.

### PR-33. Port Digest Generation Domain Logic

**Goal**

Move digest creation into Java without yet sending emails.

**Exact changes**

- Read `backend/app/services/digest_service.py`.
- Port digest selection, ranking inputs, item creation, and persistence.
- Preserve the current linkage between generated digest records and digest history views.

**Definition of done**

- Java can generate digest records and digest items consistent with current downstream consumers.

**Verification**

- Integration tests for generated digest contents and persistence.

**Risks/notes**

- If digest generation semantics drift, delivery can still "work" while content quality regresses.

### PR-34. Port Digest Email Template Rendering

**Goal**

Reproduce the digest email body generated today.

**Exact changes**

- Read `backend/app/email/templates/daily_digest.html.jinja2`.
- Port the template to the Java backend with a suitable rendering approach.
- Preserve links, sectioning, and key content decisions visible to end users.

**Definition of done**

- Java can render digest email HTML and any plain-text fallback needed by the mail flow.

**Verification**

- Render tests using representative digest fixtures.
- Snapshot-style comparison for key HTML sections.

**Risks/notes**

- Byte-for-byte HTML identity is less important than preserving user-visible content and valid rendering.

### PR-35. Port Digest Delivery Flow

**Goal**

Move the end-to-end digest email send path into Java.

**Exact changes**

- Read `backend/app/services/delivery_boundary.py`, `delivery_service_client.py`, and email-related services.
- Port digest delivery orchestration from generated digest through SMTP send and delivery recording.
- Preserve current failure handling and retry semantics where they are explicit.

**Definition of done**

- Java can deliver a digest email end to end using existing settings and persisted digest data.

**Verification**

- Integration-like tests with mock SMTP.
- Tests for delivery success and controlled failure paths.

**Risks/notes**

- SMTP remains a blocking edge. Keep the blocking boundary narrow and documented.

### PR-36. Port Internal Source-Sync Job Endpoint

**Goal**

Move the Cloud Scheduler source-sync entrypoint into Java as a standalone production-critical slice.

**Exact changes**

- Read `backend/app/api/routes/internal_jobs.py`, `backend/app/jobs/source_jobs.py`, `digest_jobs.py`, and `analysis_jobs.py`.
- Port `/internal/jobs/source-sync`.
- Preserve auth checks, request semantics, and job orchestration flow for source sync only.

**Definition of done**

- Cloud Scheduler can target the Java source-sync job entrypoint with equivalent behavior.

**Verification**

- Integration tests for authorized and unauthorized scheduler invocations.
- End-to-end tests for the source-sync job route using controlled fixtures.

**Risks/notes**

- These endpoints are production-critical because they drive the automated system behavior, not just the UI.

### PR-37. Port Internal Daily Digest Job Path

**Goal**

Make the daily-digest branch of `/internal/jobs/digests` explicit and independently shippable.

**Exact changes**

- Port the daily-digest behavior currently dispatched behind `/internal/jobs/digests`.
- Preserve the current request semantics, gating rules, digest-generation calls, and delivery orchestration for the daily cadence only.

**Definition of done**

- The Java backend can execute the daily-digest branch of `/internal/jobs/digests` with equivalent behavior.

**Verification**

- Integration tests for authorized and unauthorized invocations.
- End-to-end tests for a controlled daily-digest run.

**Risks/notes**

- Keeping daily digests separate avoids hiding a large amount of production behavior inside a generic "digest job" phase.

### PR-38. Port Internal Weekly Digest Job Path

**Goal**

Make the weekly-digest branch of `/internal/jobs/digests` explicit and independently reviewable.

**Exact changes**

- Port the weekly-digest behavior currently dispatched behind `/internal/jobs/digests`.
- Preserve cadence-specific filtering, recipient selection, and digest-generation rules used today.

**Definition of done**

- The Java backend can execute the weekly-digest branch of `/internal/jobs/digests` with equivalent behavior.

**Verification**

- Integration tests for authorized and unauthorized invocations.
- End-to-end tests for a controlled weekly-digest run.

**Risks/notes**

- Weekly behavior is easy to under-test if it stays bundled into a generic digest-job phase.

### PR-39. Port Internal Daily Observability Report Job Path

**Goal**

Make the daily observability report branch of `/internal/jobs/digests` explicit instead of hiding it under digest wording.

**Exact changes**

- Port the daily observability report behavior currently triggered behind `/internal/jobs/digests`.
- Preserve any dependency on monitoring summaries, email rendering, and delivery cadence decisions.

**Definition of done**

- The Java backend can execute the daily observability report branch of `/internal/jobs/digests` with equivalent behavior.

**Verification**

- Integration tests for authorized and unauthorized invocations.
- End-to-end tests for a controlled observability-report run.

**Risks/notes**

- This is not just another digest variant; making it explicit prevents it from being forgotten during cutover.

### PR-40. Add Shared Frontend Backend-Target Routing

**Goal**

Introduce one shared frontend mechanism that can route all API calls to either the Python backend or the Java backend.

**Exact changes**

- Update `frontend/src/lib/api.ts`, where the API root is currently derived from `VITE_CONTENT_API_ORIGIN`, so the frontend can resolve two backend origins:
  - Python backend origin
  - Java backend origin
- Keep request routing centralized in the shared API layer. Do not introduce page-specific backend-selection logic.
- Add a shared runtime backend-target state source that switches all frontend API requests together.
- Make backend-target changes trigger a full UI retargeting mechanism, for example by remounting the app subtree or invalidating all page-level data loads, so already-open pages refetch from the newly selected backend instead of mixing stale data from the previous target.
- Preserve a safe default so the existing Python backend path remains the default until later cutover phases.
- Document the constraint that both backends must remain schema-compatible and frontend-contract-compatible with the same source-of-truth database for as long as this selector exists.
- Add explicit verification that both backends accept the same frontend origin set and Firebase-authenticated browser requests while selector-based switching is enabled.

**Definition of done**

- The frontend has one shared backend-target abstraction that can route all requests to either backend without touching individual pages.
- Switching the target causes the already-open UI to refresh from the newly selected backend as one application-level transition rather than leaving page data partially stale.

**Verification**

- Frontend tests for API-root selection and request routing behavior from the shared API layer.
- Frontend tests for full-app retargeting behavior after a backend-target change.
- Verification against both backends that the same frontend origin(s) and Firebase-authenticated requests are accepted.

**Risks/notes**

- This phase must stay in shared wiring only. Per-page implementations would create permanent drift and defeat the point of the selector.

### PR-41. Add Global AppShell Backend Selector

**Goal**

Expose the backend-target switch once, globally, in the shared app chrome visible on every page for internal, staging, debug, and controlled migration validation use.

**Exact changes**

- Update `frontend/src/app/AppShell.tsx`, where the header currently renders three top summary cards.
- Add the backend selector as the fourth header block visible on every page.
- Make the selector switch the shared backend-target state created in PR-40 so every request goes to the selected backend.
- Ensure a backend-target change refreshes the whole visible UI from the newly selected backend, not just header-level data such as monitoring summary.
- Persist the selected target in a simple, explicit way suitable for debugging and side-by-side validation.
- Gate the selector so it is presented as an internal validation control during migration, not as a normal long-term product choice for end users.

**Definition of done**

- The header shows a fourth global block for backend selection on every page.
- Changing the selector flips all frontend API traffic between Python and Java through the shared API layer.
- Changing the selector causes the already-open page subtree to reload its data from the newly selected backend.

**Verification**

- Frontend interaction tests for selector rendering, persistence, and full-app request retargeting.
- Manual smoke check that changing the selector in the header affects Feed, Sources, Preferences, Settings, Digests, Want To Read, and Monitoring without page-specific wiring.

**Risks/notes**

- Keep the selector explicit and visible where migration validation needs it, but do not redefine normal production UX around backend choice.

### PR-42. Add Local Dual-Backend Smoke Coverage and Workflow Docs

**Goal**

Make local and preview verification practical once the shared selector exists.

**Exact changes**

- Add or update smoke tests/scripts so core frontend flows can be exercised against both backends through the shared selector.
- Document the local migration workflow:
  - run frontend once
  - run Python and Java backends in parallel
  - switch the selector in `AppShell`
  - verify both backends operate correctly against the same database
- Include local checks that both backends accept the same frontend origin and Firebase-authenticated browser requests when selected through the shared frontend.
- Keep the workflow repo-specific and grounded in the current frontend structure.

**Definition of done**

- Developers can run one frontend build and switch it between Python and Java locally while both backends point at the same database.

**Verification**

- Frontend smoke run against both backends for Feed, Sources, Preferences, Settings, Digests, Want To Read, and Monitoring as routes become available.

**Risks/notes**

- The point of this phase is not just convenience. It proves the selector model, full-app retargeting behavior, and dual-backend compatibility before shared-environment use.

### PR-43. Add Python-vs-Java Contract Test Harness

**Goal**

Create an automated safety net that compares both implementations before cutover.

**Exact changes**

- Build a contract test harness that runs representative API calls against both backends on the same test dataset.
- Start with the highest-value routes:
  - posts
  - feedback
  - preferences
  - settings
  - sources
  - digests
  - monitoring
- Add comparison helpers for status, response shape, ordering-sensitive fields, and key business values.
- Make schema- and contract-compatibility drift during the parallel-run window a release-blocking concern, not just an informational warning.

**Definition of done**

- The team can automatically detect meaningful contract drift between Python and Java on migrated routes.

**Verification**

- Run the contract suite and inspect at least one intentionally mismatched case to prove failures are actionable.

**Risks/notes**

- This should be treated as a release-quality safety layer, not as optional test polish.

### PR-44. Add Java Image Build and Publish Path in GitHub Actions

**Goal**

Make `backend-java` buildable and publishable in GitHub Actions before wiring deployment targets.

**Exact changes**

- Extend `.github/workflows/deploy.yml` or add a dedicated Java deploy-support workflow.
- Add:
  - Java image build for `backend-java`
  - image push to Artifact Registry
- Preserve the existing Python production deploy path while Java is still parallel.

**Definition of done**

- GitHub Actions can build and publish a Java backend image without deploying it anywhere yet.

**Verification**

- Successful workflow run that builds and pushes the Java image.

**Risks/notes**

- Splitting build/publish from deploy keeps failures smaller and easier to debug in one session.

### PR-45. Add Java Flyway Migration Path in GitHub Actions

**Goal**

Wire database migration execution for Java as a standalone deploy concern.

**Exact changes**

- Extend the Java deploy workflow path with a Flyway migration execution strategy suitable for Cloud Run deployment.
- Reuse the same secret sources and DB wiring already used by the current Python migration job where possible.

**Definition of done**

- GitHub Actions can trigger Java-backed schema migration execution without also needing to complete the service deploy.

**Verification**

- Successful workflow run against a non-production database target.

**Risks/notes**

- Keeping migrations separate from service deploy is safer because schema failures deserve their own review surface.

### PR-46. Add Non-Production Cloud Run Deploy Path for `backend-java`

**Goal**

Prepare the Java service for deployable preview and staging environments before traffic cutover.

**Exact changes**

- Extend the Java deploy path with:
  - a Cloud Run deploy target for the Java service, separate from the production Python service
  - env and secret wiring for:
    - database URL
    - app master key
    - Gemini API key
    - Firebase project id
    - allowed emails
    - scheduler invoker
    - public origins
- Preserve the existing Python production deploy path while Java is still parallel.
- Verify that Python and Java are both configured to accept the same allowed frontend origin set and the same Firebase-authenticated browser request pattern needed by selector-driven switching.

**Definition of done**

- GitHub Actions can build and deploy a separate Java backend instance to Cloud Run without affecting the current production FastAPI service.

**Verification**

- Successful workflow run that deploys the Java service to a non-production Cloud Run target.
- Smoke check of `/api/health` on the deployed Java service.
- Explicit CORS/public-origin and authenticated-browser-request smoke checks against both backend targets.

**Risks/notes**

- Keep the Java service isolated from the current production Cloud Run target until cutover phases explicitly begin.

### PR-47. Add Staging Hosting or Preview-Channel Frontend Path for the Shared Selector

**Goal**

Create an executable staging frontend path that can switch between Python and Java backends through the shared selector.

**Exact changes**

- Add a staging Hosting target or Firebase preview-channel deployment path that can be built with both staging backend origins available to the shared selector.
- Update the build-time variable plan so it no longer assumes one baked `VITE_CONTENT_API_ORIGIN` for all staging validation.
- Document how the shared selector is configured in staging and how staging hosting differs from production hosting.
- Keep the selector scoped to internal/staging validation use rather than positioning it as a normal user-facing product control.
- Keep the current production hosting path unchanged.

**Definition of done**

- The repo has a documented and automatable way to publish a staging frontend build whose shared selector can target either staging backend.

**Verification**

- Successful staging or preview-channel frontend deployment with both backend origins configured for the selector.
- Manual smoke check that the staged frontend can switch between the staging Python backend and the staging Java backend.

**Risks/notes**

- Without this phase, the shared selector exists only locally and "switch staging frontend" is not actually executable in one PR.

### PR-48. Deploy Java Backend to Staging

**Goal**

Run the Java backend as a real service in a shared environment before any production traffic shift.

**Exact changes**

- Create or wire a staging deployment target for `backend-java`.
- Point staging env vars and secrets to safe staging resources.
- Document staging URLs and operational checks.

**Definition of done**

- A shared staging environment exists where the Java backend runs independently and can be exercised end to end.

**Verification**

- Smoke tests for public health, authenticated API access, source sync, and digest history against staging.

**Risks/notes**

- Do not treat "it starts" as sufficient. The point of staging is system behavior, not only boot success.

### PR-49. Deploy Staging Frontend With the Shared Backend Selector

**Goal**

Use staging to validate realistic UI behavior while the same frontend can target either backend against the same staging database.

**Exact changes**

- Deploy the staging Hosting target or preview channel created in PR-47 with the shared backend selector enabled.
- Configure the selector so staging users can switch between the staging Python backend and the staging Java backend.
- Keep rollback instructions explicit for the staging frontend only.
- Verify that both staging backends accept the same staging frontend origin and Firebase-authenticated browser requests during selector-driven validation.

**Definition of done**

- Staging UI exposes the shared backend selector and can exercise both backends against the same staging database.

**Verification**

- End-to-end smoke of Feed, Sources sync, Preferences recompute, Settings test email, Digest history, and Monitoring in staging against both selector targets.
- Explicit smoke checks for full-page retargeting after a selector change and for equivalent CORS/auth acceptance on both staging backends.

**Risks/notes**

- This is the first shared-environment proof that both backends can operate in parallel while the frontend chooses the target.

### PR-50. Point Staging Scheduler to Java Internal Jobs

**Goal**

Complete the staging rehearsal by moving scheduled automation after backend and frontend staging paths are already proven.

**Exact changes**

- Point staging Cloud Scheduler or equivalent job triggers at Java internal-job endpoints.
- Keep rollback instructions explicit for staging jobs.

**Definition of done**

- Staging scheduled jobs run against Java rather than Python.

**Verification**

- End-to-end smoke of source-sync, daily digest, weekly digest, and observability-report job paths in staging.

**Risks/notes**

- This split is deliberate. Combining backend deploy, frontend deploy, and scheduler cutover in one PR is too large for one session.

### PR-51. Deploy Production Frontend With the Shared Backend Selector

**Goal**

Ship the selector-driven frontend path to production only as a controlled migration-validation mechanism while keeping Python as the default backend target for normal users.

**Exact changes**

- Deploy the shared backend selector to the production frontend.
- Configure production frontend builds with both production backend origins available to the shared selector.
- Keep Python as the default selected target at first.
- Gate access to the selector for internal/support/controlled-validation use during migration instead of treating it as a general user-facing choice.
- Make the rollback behavior explicit: controlled validation sessions can still route all browser requests back to Python during the soak period.
- Verify that both production backends accept the same production frontend origin set and Firebase-authenticated browser requests needed for controlled selector use.

**Definition of done**

- The production frontend contains the shared selector path for controlled migration validation, while ordinary production UX still defaults to Python without redefining backend choice as a normal user control.

**Verification**

- Manual smoke checks of selector-driven traffic to both backends in controlled production-validation sessions.
- Runtime dashboards for error rate and latency on both production backend targets.

**Risks/notes**

- Because the selector switches all browser requests together, this phase is a better controlled validation step than trying to split read traffic from write traffic inside the same UI flow.

### PR-52. Switch the Production Frontend Default Target to Java

**Goal**

Make Java the default backend for browser traffic after parallel validation is complete.

**Exact changes**

- Change the production frontend default backend target from Python to Java.
- Keep the shared selector available only for internal/support/controlled rollback validation during the soak period.
- Confirm that all browser-driven routes now work correctly when the Java backend is the default selected target.
- Keep the requirement explicit that Python remains schema- and contract-compatible enough for rollback until the selector/parallel-run window is closed.

**Definition of done**

- Production browser traffic defaults to Java, and controlled rollback validation to Python remains available during the confidence window without turning backend choice into a permanent end-user control.

**Verification**

- Business smoke checks across both read and write UI flows with Java as the default selected backend.
- Monitoring for increased 4xx/5xx, latency regressions, and data-consistency issues while both backends still operate against the same database.

**Risks/notes**

- This phase intentionally flips all browser-driven traffic together because the selector model is all-or-nothing per session, not per route group.
- Do not close the selector/parallel-run window until rollback validation proves Python still works against the shared schema and data.

### PR-53. Shift Production Internal Jobs and Digest Delivery

**Goal**

Complete the backend cutover by moving automated production behavior to Java.

**Exact changes**

- Point production Cloud Scheduler jobs at the Java backend.
- Move digest generation and delivery ownership to Java.
- Confirm Cloud Run service account, OIDC audience, and secret wiring are all correct on the Java side.

**Definition of done**

- Source sync, digest generation, and digest delivery run in production through Java.

**Verification**

- Successful source-sync job run.
- Successful digest job run.
- Delivery confirmation for a controlled digest cycle.

**Risks/notes**

- This is the most operationally sensitive production switch because failures may not be user-driven or instantly visible.

### PR-54. Retire Python Backend from the Active Production Path

**Goal**

Finish the migration and remove the old backend from normal delivery flow.

**Exact changes**

- Remove the Python backend from the active Cloud Run production path after a stability window.
- Update CI/CD and operational docs to make Java the primary backend.
- Keep rollback/archive strategy explicit according to team policy.

**Definition of done**

- Java is the sole active production backend path.
- Team docs and deployment automation reflect the new reality.

**Verification**

- Full regression smoke.
- Review of CI, deploy workflows, and README for consistency with the new architecture.

**Risks/notes**

- Do not rush this phase. Keep the Python path available until the Java service has earned operational trust.

## Per-PR Working Rules

- Every implementation PR starts on a dedicated branch, not on `master`.
- Every PR includes only one phase's scope plus any minimal supporting tests/docs required to keep the repo healthy.
- Every PR ends with relevant verification run locally and in CI. For Java backend work, PR-03 establishes the dedicated GitHub Actions coverage that all later Java phases are expected to use; PR-02 is the only bootstrap exception and should merge immediately before PR-03.
- Every PR gets review focused on correctness, contract compatibility, and reactive-stack discipline.
- No PR should defer critical behavior with comments like "wire later" when that behavior is already part of the live Python backend contract.
- Frontend backend-target work stays centralized in shared wiring such as `frontend/src/lib/api.ts` and `frontend/src/app/AppShell.tsx`; do not split that migration into separate per-page implementations.
