# Reactive Java Backend Migration Plan

## Principles and Constraints

- Target stack: Java 21, Spring Boot 3, WebFlux, Reactor, Maven, R2DBC, Flyway.
- Migration is incremental. The current FastAPI backend in `backend/` stays operational until Java takes over each contract.
- Each phase must fit in one GPT-5.4 mini session, end in one merged PR, and leave the repo in a working state.
- Runtime paths must stay fully reactive: WebFlux controllers, Reactor services, R2DBC persistence, WebClient for HTTP integrations. Do not introduce JPA or JDBC into request-processing code.
- Existing backend behavior is the source of truth at first: keep current API shapes, auth rules, DB semantics, scheduler entrypoints, and operational topology before attempting cleanup.
- Existing deployment model matters: today the backend is a FastAPI monolith on Cloud Run, migrations run through a Cloud Run job, CI is in `.github/workflows/ci.yml`, and deploy is in `.github/workflows/deploy.yml`.
- Keep the new backend in a separate module such as `backend-java/` until cutover is complete.
- Cloud Run, Firebase Auth, Gemini, Gmail SMTP, Secret Manager, and Neon Postgres all need explicit migration steps. None of them should be treated as "will wire later".
- Blocking libraries may still exist at the edges, especially SMTP, HTML parsing, and some crypto operations. If blocking code cannot be avoided, isolate it explicitly away from the Netty event loop and document the scheduler choice in the PR.

## PR Phases

### PR-01. Freeze Migration Scope and Current Contracts

**Goal**

Create a single source of truth for what the Java backend must replace.

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
- Capture operational dependencies from the current repo:
  - FastAPI on Cloud Run
  - Alembic migrations
  - Firebase Auth plus backend email allowlist
  - Gemini integration
  - Gmail SMTP digest delivery
  - Secret Manager secrets
  - Cloud Scheduler OIDC calls
- Add a migration inventory document that maps Python modules to planned Java packages.

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

### PR-03. Port Configuration and Environment Contract

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

### PR-04. Add Health, Actuator, and Observability Baseline

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

### PR-05. Establish Reactive Postgres Connectivity

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

### PR-06. Port Alembic Schema to Flyway

**Goal**

Make Java responsible for the same schema shape as the Python backend.

**Exact changes**

- Translate the existing Alembic migrations in `backend/alembic/versions/` into ordered Flyway SQL migrations under `backend-java/src/main/resources/db/migration/`.
- Preserve tables and relationships used by:
  - sources
  - posts
  - feedback
  - preference profiles
  - settings
  - read later
  - digests
  - digest items
  - post analysis
- Document any Alembic behavior that does not translate one-to-one and how it is handled.

**Definition of done**

- A clean database can be created from Flyway alone and matches the Python backend's current schema expectations.

**Verification**

- Testcontainers migration test on an empty DB.
- Schema assertion tests for key tables and columns.

**Risks/notes**

- Avoid trying to "improve" the schema during the port. Stack migration and schema redesign together is a bad trade.

### PR-07. Build Reactive Security Foundation

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

### PR-08. Define Shared Error and DTO Contract

**Goal**

Freeze API serialization and error semantics before porting business logic route by route.

**Exact changes**

- Port the active Pydantic request and response shapes from `backend/app/schemas/` into Java DTOs.
- Add validation annotations to mirror existing FastAPI validation.
- Add global exception mapping for the expected HTTP status patterns.
- Document any deliberately preserved quirks in current API behavior.

**Definition of done**

- DTOs exist for all active route groups.
- Error handling is centralized and consistent with the current backend contract.

**Verification**

- Serialization tests.
- Validation tests.
- Exception handler integration tests.

**Risks/notes**

- "Cleaner" Spring errors are not the goal yet. Contract compatibility is.

### PR-09. Port `/api/posts` Read Path

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

### PR-10. Port Want-to-Read Endpoints

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

### PR-11. Port Feedback Endpoints

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

### PR-12. Port Preferences Read API

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

### PR-13. Port Preferences Recompute Flow

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

### PR-14. Port Settings Read and Update API

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

### PR-15. Port Secret Handling and SMTP Credential Compatibility

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

### PR-16. Port Test Email Flow

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

### PR-17. Port Digest History Read API

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

### PR-18. Port Sources Read API

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

### PR-19. Port Sources CRUD

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

### PR-20. Create Shared Reactive External HTTP Client Layer

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

### PR-21. Port Source Discovery and Parsing Foundation

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

### PR-22. Port Single-Source Sync

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

### PR-23. Port Bulk Source Sync

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

### PR-24. Port Reload/Refresh Source Post Flows

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

### PR-25. Port Analysis Domain Flow Without LLM

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

### PR-26. Port Gemini Reactive Client

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

### PR-27. Port Monitoring API

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

### PR-28. Port Digest Generation Domain Logic

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

### PR-29. Port Digest Email Template Rendering

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

### PR-30. Port Digest Delivery Flow

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

### PR-31. Port Internal Job Endpoints

**Goal**

Move Cloud Scheduler entrypoints into Java.

**Exact changes**

- Read `backend/app/api/routes/internal_jobs.py`, `backend/app/jobs/source_jobs.py`, `digest_jobs.py`, and `analysis_jobs.py`.
- Port `/internal/jobs/source-sync` and `/internal/jobs/digests`.
- Preserve auth checks, request semantics, and job orchestration flow.

**Definition of done**

- The same Cloud Scheduler calls can target the Java backend and invoke equivalent job behavior.

**Verification**

- Integration tests for authorized and unauthorized scheduler invocations.
- End-to-end tests for both job routes using controlled fixtures.

**Risks/notes**

- These endpoints are production-critical because they drive the automated system behavior, not just the UI.

### PR-32. Add Frontend-to-Java Local Switch and Smoke Coverage

**Goal**

Make local and preview verification practical before shared environments are switched.

**Exact changes**

- Add a backend target switch for frontend development so the React app can point to `backend-java`.
- Add or update smoke tests/scripts so core frontend flows can be exercised against Java for already-ported routes.
- Document the local dual-backend workflow during migration.

**Definition of done**

- Developers can run the frontend against the Java backend locally without breaking the existing Python local path.

**Verification**

- Frontend smoke run against Java for Feed, Sources, Preferences, Settings, Digest, and Monitoring pages as routes become available.

**Risks/notes**

- Keep the switch explicit. Silent target flips during migration will confuse local debugging.

### PR-33. Add Python-vs-Java Contract Test Harness

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

**Definition of done**

- The team can automatically detect meaningful contract drift between Python and Java on migrated routes.

**Verification**

- Run the contract suite and inspect at least one intentionally mismatched case to prove failures are actionable.

**Risks/notes**

- This should be treated as a release-quality safety layer, not as optional test polish.

### PR-34. Add GitHub CI for `backend-java`

**Goal**

Introduce first-class GitHub CI for the Java backend before any shared-environment cutover work.

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

- This step was missing before and must land before staging or production cutover. Without it, the migration has no trustworthy automated gate for the new backend.

### PR-35. Add GitHub CD Path for `backend-java` to Cloud Run

**Goal**

Prepare the Java service for deployable preview and staging environments before traffic cutover.

**Exact changes**

- Extend `.github/workflows/deploy.yml` or add a dedicated Java deploy workflow.
- Add:
  - Java image build for `backend-java`
  - image push to Artifact Registry
  - Flyway migration execution strategy for Java
  - Cloud Run deploy target for the Java service, separate from the production Python service
  - env and secret wiring for:
    - database URL
    - app master key
    - Gemini API key
    - Firebase project id
    - allowed emails
    - scheduler invoker
    - public origins
- Preserve the existing Python production deploy path while Java is still parallel.

**Definition of done**

- GitHub Actions can build and deploy a separate Java backend instance to Cloud Run without affecting the current production FastAPI service.

**Verification**

- Successful workflow run that deploys the Java service to a non-production Cloud Run target.
- Smoke check of `/api/health` on the deployed Java service.

**Risks/notes**

- Keep the Java service isolated from the current production Cloud Run target until cutover phases explicitly begin.

### PR-36. Deploy Java Backend to Staging

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

### PR-37. Switch Staging Frontend and Scheduler to Java

**Goal**

Use staging to validate realistic end-to-end behavior, including jobs.

**Exact changes**

- Point the staging frontend at the staging Java backend.
- Point staging Cloud Scheduler or equivalent job triggers at Java internal-job endpoints.
- Keep rollback instructions explicit.

**Definition of done**

- Staging UI flows and scheduled jobs run against Java rather than Python.

**Verification**

- End-to-end smoke of Feed, Sources sync, Preferences recompute, Settings test email, Digest history, Monitoring, and internal jobs in staging.

**Risks/notes**

- This is the first full-system rehearsal. Expect integration bugs and keep rollback easy.

### PR-38. Shift Production Read Traffic to Java

**Goal**

Start production cutover with the lowest-risk traffic class.

**Exact changes**

- Route production read-heavy endpoints to Java while leaving higher-risk write and job paths on Python.
- Keep rollback controls simple and documented.

**Definition of done**

- Production read endpoints are served by Java with acceptable correctness, latency, and error rates.

**Verification**

- Runtime dashboards for error rate and latency.
- Manual smoke checks of feed, source list, digest history, preferences, and monitoring.

**Risks/notes**

- Read traffic is safer than writes, but contract mismatches still surface here first.

### PR-39. Shift Production Write Traffic to Java

**Goal**

Move user state-changing flows after read stability is proven.

**Exact changes**

- Route feedback, want-to-read, settings updates, and sources CRUD writes to Java.
- Preserve rollback options per route group if infrastructure allows.

**Definition of done**

- User writes go to Java successfully and persist correctly.

**Verification**

- Business smoke checks for each write path.
- Monitoring for increased 4xx/5xx or write-latency regressions.

**Risks/notes**

- This is a much higher-risk cutover than read traffic because state consistency becomes visible immediately.

### PR-40. Shift Production Internal Jobs and Digest Delivery

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

### PR-41. Retire Python Backend from the Active Production Path

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
- Every PR ends with relevant verification run locally and in CI.
- Every PR gets review focused on correctness, contract compatibility, and reactive-stack discipline.
- No PR should defer critical behavior with comments like "wire later" when that behavior is already part of the live Python backend contract.
