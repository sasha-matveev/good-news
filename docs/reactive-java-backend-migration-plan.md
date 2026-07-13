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

### PR-02. Create the `backend-java` Maven Skeleton [Completed on master]

**Goal**

Introduce a minimal Java backend module that builds and starts.

**Status**

- Completed on `master`.
- Artifact: `backend-java/` Maven skeleton, including `backend-java/pom.xml`, `backend-java/src/main/java/com/goodnews/backendjava/BackendJavaApplication.java`, and `backend-java/src/test/java/com/goodnews/backendjava/BackendJavaApplicationTests.java`.
- Reviewed implementation basis for this plan update: commit `100046d` (`feat: create backend-java maven skeleton`).

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

### PR-03. Add GitHub CI for `backend-java` [Completed on master]

**Goal**

Introduce first-class GitHub CI for the Java backend before feature migration begins.

**Status**

- Completed on `master`.
- Artifact: `.github/workflows/ci.yml`, including the `backend-java` GitHub Actions job with Maven verification and Maven dependency caching.
- Reviewed implementation basis for this plan update: current `master` CI state after commits `2fbe8e2` (`ci: add backend-java CI job`) and `d133af1` (`fix: restore unconditional backend and frontend ci`).

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

### PR-04. Port Configuration and Environment Contract [Completed on master]

**Goal**

Reproduce the current backend config surface in Spring configuration classes.

**Status**

- Completed on `master`.
- Artifact: `backend-java` configuration contract under `backend-java/src/main/java/com/goodnews/backendjava/config/`, plus binding and validation coverage in `backend-java/src/test/java/com/goodnews/backendjava/config/`.
- Reviewed implementation basis for this plan update: current `master` config state after commits `a83189b` (`feat: add spring port config contract`), `e3cb9ab` (`fix: align config validation with python contract`), and `fff06cc` (`refactor: narrow backend-java config contract`).
- Scope note: the Grafana / observability-specific configuration slice was intentionally excluded from this step and is not part of the completion mark for `PR-04`.

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

### PR-05. Add Health, Actuator, and Observability Baseline [Completed on master]

**Goal**

Stand up the minimum operational surface expected from the backend.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/java/com/goodnews/backendjava/config/ActuatorSecurityConfig.java`, `backend-java/src/main/resources/application.yml`, `backend-java/src/test/java/com/goodnews/backendjava/ActuatorEndpointsTest.java`, and `backend-java/README.md`.
- Reviewed implementation basis for this plan update: current `master` observability baseline in commit `d7af24d` (`feat: add backend-java observability baseline`).
- Scope note: the Grafana / observability-dashboard-specific slice was intentionally excluded from this step and is not part of the completion mark for `PR-05`.
- Scope note: the current `master` implementation exposes the public health baseline through `/actuator/health` and `/actuator/prometheus`.

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

### PR-06. Establish Reactive Postgres Connectivity [Completed on master]

**Goal**

Connect Java to Postgres the reactive way before any domain migration.

**Status**

- Completed on `master`.
- Artifact: reactive database connectivity under `backend-java/src/main/java/com/goodnews/backendjava/config/`, including `ReactiveDatabaseConfig.java`, `ReactiveDatabaseSmokeProbe.java`, and `ReactiveDatabaseHealthIndicator.java`, plus integration and configuration coverage in `backend-java/src/test/java/com/goodnews/backendjava/`.
- Reviewed implementation basis for this plan update: current `master` connectivity state after commits `392ba19` (`feat: establish reactive postgres connectivity`) and `f3a1a80` (`fix: preserve reactive postgres url semantics`).

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

### PR-07. Port Core Content Schema to Flyway [Completed on master]

**Goal**

Start Flyway migration parity with the core content tables that unlock the first API slices.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/resources/db/migration/V1__core_schema.sql`, `backend-java/src/main/resources/db/migration/V2__posts_and_feedback.sql`, and `backend-java/src/test/java/com/goodnews/backendjava/FlywaySchemaMigrationIT.java`.
- Reviewed implementation basis for this plan update: current `master` Flyway schema state after commit `9348aeb` (`feat: port alembic schema to flyway`) and follow-up Flyway fixes `c35bce0`, `5b21f03`, `df7aed0`, and `4409911`.
- Scope note: `master` implemented `PR-07`..`PR-09` as one broader Flyway parity slice rather than three separate PRs.

**Exact changes**

- Translate the Alembic schema needed for:
  - sources
  - posts
  - feedback
  - preference profiles
- Preserve keys, relationships, and table semantics expected by the Python backend.

**Definition of done**

- A clean database can be created with the core content tables needed by the first user-facing read and feedback routes.

**Verification**

- Testcontainers migration test on an empty DB.
- Schema assertion coverage in `FlywaySchemaMigrationIT`.

**Risks/notes**

- Avoid trying to "improve" the schema during the port. Stack migration and schema redesign together is a bad trade.

### PR-08. Port Settings and Read-Later Schema to Flyway [Completed on master]

**Goal**

Add the user-settings tables needed for settings and want-to-read flows.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/resources/db/migration/V4__read_later.sql` and shared Flyway verification in `backend-java/src/test/java/com/goodnews/backendjava/FlywaySchemaMigrationIT.java`.
- Reviewed implementation basis for this plan update: current `master` Flyway schema state after commit `9348aeb` (`feat: port alembic schema to flyway`) and follow-up Flyway fixes `c35bce0`, `5b21f03`, `df7aed0`, and `4409911`.
- Scope note: `master` implemented `PR-07`..`PR-09` as one broader Flyway parity slice rather than three separate PRs.

**Exact changes**

- Translate the Alembic schema for:
  - settings
  - read later
- Preserve keys, nullability, defaults, and uniqueness rules relied on by the Python service.

**Definition of done**

- A clean database can be created with settings and read-later tables on top of the core content schema.

**Verification**

- Testcontainers migration test on an empty DB.
- Schema assertion coverage in `FlywaySchemaMigrationIT`.

**Risks/notes**

- Keep Java and Python schema expectations aligned while both backends operate against the same database.

### PR-09. Port Digest and Analysis Schema to Flyway [Completed on master]

**Goal**

Finish Flyway schema parity for digest and analysis features.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/resources/db/migration/V3__digests.sql` and shared Flyway verification in `backend-java/src/test/java/com/goodnews/backendjava/FlywaySchemaMigrationIT.java`.
- Reviewed implementation basis for this plan update: current `master` Flyway schema state after commit `9348aeb` (`feat: port alembic schema to flyway`) and follow-up Flyway fixes `c35bce0`, `5b21f03`, `df7aed0`, and `4409911`.
- Scope note: `master` implemented `PR-07`..`PR-09` as one broader Flyway parity slice rather than three separate PRs.

**Exact changes**

- Translate the Alembic schema for:
  - digests
  - digest items
  - post analysis
- Preserve foreign keys and retention/history assumptions currently visible to the Python backend and UI.

**Definition of done**

- A clean database can be created with digest and analysis tables on top of the earlier Flyway phases.

**Verification**

- Testcontainers migration test on an empty DB.
- Schema assertion coverage in `FlywaySchemaMigrationIT`.

**Risks/notes**

- Schema parity is now good enough to support the rest of the Java migration against the shared database.

### PR-10. Build Reactive Security, DTO, and Error-Contract Foundation [Completed on master]

**Goal**

Establish the shared contract layer once so later API ports can be mostly domain work rather than repeated plumbing.

**Status**

- Completed on `master`.
- Artifact: reactive security, DTO, validation, and error-contract foundation under `backend-java/src/main/java/com/goodnews/backendjava/api/`, `backend-java/src/main/java/com/goodnews/backendjava/security/`, and `backend-java/src/main/java/com/goodnews/backendjava/validation/`, with contract coverage in `backend-java/src/test/java/com/goodnews/backendjava/api/` and `backend-java/src/test/java/com/goodnews/backendjava/security/`.
- Reviewed implementation basis for this plan update: current `origin/master` head commit `26011df` (`feat: add reactive security dto and error foundation`).
- Scope note: the DTO layer in `master` covers the listed contract groups by porting the active Python request/response shapes from `backend/app/schemas/` and the route-local contract shapes currently defined under `backend/app/api/routes/`.
- Scope note: the current `master` security foundation keeps `/api/*` open when Firebase auth is not configured and returns `503` for `/internal/jobs/*` when the scheduler invoker is unset; both behaviors are covered by contract tests in the same phase.

**Exact changes**

- Port the current auth model from `backend/app/core/request_auth.py` into Spring Security WebFlux.
- Support:
  - Firebase token verification
  - backend email allowlist behavior
  - Cloud Scheduler OIDC invoker checks for `/internal/jobs/*`
- Port the active Pydantic request and response shapes from `backend/app/schemas/` into Java DTOs for:
  - posts
  - feedback
  - preferences
  - settings
  - want to read
  - sources
  - digests
  - monitoring
  - internal job payloads and wrappers that are part of the current contract
- Add validation annotations to mirror current FastAPI behavior.
- Add shared exception mapping so Java returns the same class of HTTP errors the frontend and internal callers already expect.

**Definition of done**

- Security rules, DTO serialization, validation, and global error handling are in place for all currently known route groups.

**Verification**

- Security integration tests for public, user-authenticated, and scheduler-authenticated flows.
- Serialization and validation tests across representative DTOs.
- Exception-handler contract tests.

**Risks/notes**

- This phase is intentionally broader than before because splitting auth, DTOs, and validation produced too much overhead and too little executable value.

### PR-11. Port Feed, Feedback, and Want-to-Read APIs [Completed on master]

**Goal**

Move the first complete set of user-facing feed interactions into Java.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/java/com/goodnews/backendjava/api/PostsController.java`, `backend-java/src/main/java/com/goodnews/backendjava/api/FeedbackController.java`, `backend-java/src/main/java/com/goodnews/backendjava/api/WantToReadController.java`, related services under `backend-java/src/main/java/com/goodnews/backendjava/service/`, and integration coverage in `backend-java/src/test/java/com/goodnews/backendjava/api/FeedFeedbackWantToReadApiTest.java`.
- Reviewed implementation basis for this plan update: current `master` API state after commit `156e6b1` (`feat: port backend-java feed and feedback api`) and follow-up fix `e177902` (`fix: harden post row mapping for postgres`).

**Exact changes**

- Port `/api/posts` read behavior from `backend/app/api/routes/posts.py` and related services.
- Preserve sorting semantics such as "By match" and "By date", plus filtering, pagination, and response enrichment.
- Port feedback read/write behavior from `backend/app/api/routes/feedback.py`.
- Port want-to-read read/write behavior from `backend/app/api/routes/want_to_read.py`.
- Preserve idempotency and state-transition semantics used by the current frontend.

**Definition of done**

- The main feed, explicit feedback flows, and want-to-read flows work through Java without frontend changes.

**Verification**

- Integration tests with seeded data for feed reads, feedback updates, and read-later add/remove/list flows.
- Contract comparison against Python for representative scenarios.

**Risks/notes**

- This is the first real frontend-visible parity slice, so response ordering and state semantics matter more than internal code elegance.

### PR-12. Port Preferences and Settings Domain End to End [Completed on master]

**Goal**

Move user preference and settings ownership into Java, including secret compatibility and test-email behavior.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/java/com/goodnews/backendjava/api/PreferencesController.java`, `backend-java/src/main/java/com/goodnews/backendjava/api/SettingsController.java`, `backend-java/src/main/java/com/goodnews/backendjava/service/PreferenceService.java`, `backend-java/src/main/java/com/goodnews/backendjava/service/SettingsService.java`, `backend-java/src/main/java/com/goodnews/backendjava/service/TestEmailService.java`, `backend-java/src/main/java/com/goodnews/backendjava/service/JakartaMailSmtpEmailAdapter.java`, and coverage in `backend-java/src/test/java/com/goodnews/backendjava/api/PreferencesSettingsApiTest.java` plus `backend-java/src/test/java/com/goodnews/backendjava/service/SettingsServiceCryptoCompatibilityTest.java`.
- Reviewed implementation basis for this plan update: current `master` preferences/settings state after commit `03f52d4` (`feat: port preferences and settings domain`) and follow-up fix `0b3b243` (`fix: restore settings defaults and master key resolution`).

**Exact changes**

- Port preferences read and recompute flows from `backend/app/api/routes/preferences.py` and related services.
- Preserve the dependency chain between posts, feedback, and persisted preference output.
- Port settings read and update behavior from `backend/app/api/routes/settings.py` and `backend/app/services/settings_service.py`.
- Port app master key handling and SMTP credential encryption/decryption compatibility from `backend/app/core/secrets.py`.
- Port the Settings "send test email" action behind a dedicated SMTP adapter.
- Explicitly isolate blocking SMTP work away from the Netty event loop.

**Definition of done**

- Preferences and settings screens can fully operate through Java, including recompute, SMTP credential compatibility, and test-email sending.

**Verification**

- Integration tests for preference reads and recompute.
- API integration tests for valid and invalid settings updates.
- Fixed-vector tests for cross-language secret compatibility.
- Mock-SMTP tests for the test-email flow.

**Risks/notes**

- This is intentionally one larger slice because settings without secret compatibility or test email is not actually deployable.

### PR-13. Port Digest History and Source Management APIs [Completed on master]

**Goal**

Move the remaining interactive CRUD-style APIs needed by the existing frontend before deeper background workflows.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/java/com/goodnews/backendjava/api/DigestsController.java`, `backend-java/src/main/java/com/goodnews/backendjava/api/SourcesController.java`, `backend-java/src/main/java/com/goodnews/backendjava/service/DigestHistoryService.java`, `backend-java/src/main/java/com/goodnews/backendjava/service/SourceManagementService.java`, and coverage in `backend-java/src/test/java/com/goodnews/backendjava/api/DigestSourceApiTest.java` plus `backend-java/src/test/java/com/goodnews/backendjava/service/SourceManagementServiceTest.java`.
- Reviewed implementation basis for this plan update: current `master` digest/source API state after commit `cd38fc4` (`feat: port digest history and source APIs`).

**Exact changes**

- Port digest history list/detail reads from `backend/app/api/routes/digests.py`.
- Port source listing, detail/log reads, and full source CRUD from `backend/app/api/routes/sources.py`.
- Preserve URL validation, duplicate handling, source status fields, and nested digest item response structures.

**Definition of done**

- Digests and Sources screens can read and manage their primary data through Java without frontend changes.

**Verification**

- Integration tests for digest list/detail responses.
- Integration tests for source list/detail/create/update/delete and duplicate URL handling.

**Risks/notes**

- This phase deliberately stops before sync orchestration because CRUD and ingestion fail in different ways and should not be debugged together.

### PR-14. Port Source Ingestion Foundation and Single-Source Sync [Completed on master]

**Goal**

Build the reusable ingestion base and prove one end-to-end sync path.

**Status**

- Completed on `master`.
- Artifact: ingestion foundation under `backend-java/src/main/java/com/goodnews/backendjava/ingestion/`, including `ingestion/infrastructure/http/WebClientSourceDocumentLoader.java`, parsing and known-site strategy packages, `backend-java/src/main/java/com/goodnews/backendjava/ingestion/application/SyncSingleSource.java`, the public sync route in `backend-java/src/main/java/com/goodnews/backendjava/api/SourcesController.java`, and coverage in `backend-java/src/test/java/com/goodnews/backendjava/ingestion/` plus `backend-java/src/test/java/com/goodnews/backendjava/service/SingleSourceSyncServiceIT.java`.
- Reviewed implementation basis for this plan update: current `master` ingestion state after commit `f2e4429` (`feat: port source ingestion foundation`).

**Exact changes**

- Add a shared reactive `WebClient` layer with timeout, retry, error-mapping, and logging policy.
- Port source discovery and parsing helpers from `backend/app/parsing/*`.
- Preserve known-site adaptations that are still active.
- Port single-source sync from `backend/app/services/source_sync.py`, including:
  - fetch
  - parse
  - deduplicate
  - persist posts
  - update source state
- Explicitly isolate CPU-heavy or blocking parsing work away from the event loop where needed.

**Definition of done**

- Java can fetch and parse representative source content and successfully complete one source sync end to end.

**Verification**

- Unit tests for parsing fixtures and HTTP-client behavior.
- Integration tests for single-source sync, duplicate post handling, and source status updates.

**Risks/notes**

- Keep concurrency intentionally simple here. The goal is correctness of the pipeline, not throughput tuning yet.

### PR-15. Port Bulk Source Sync, Reload Flows, and Monitoring API [Completed on master]

**Goal**

Complete the ingestion and operational visibility slice as one coherent unit.

**Status**

- Completed on `master`.
- Artifact: `backend-java/src/main/java/com/goodnews/backendjava/ingestion/application/SyncActiveSources.java`, `backend-java/src/main/java/com/goodnews/backendjava/ingestion/application/ReloadSourcePosts.java`, `backend-java/src/main/java/com/goodnews/backendjava/api/MonitoringController.java`, the extended sync/reload routes in `backend-java/src/main/java/com/goodnews/backendjava/api/SourcesController.java`, and monitoring persistence under `backend-java/src/main/java/com/goodnews/backendjava/monitoring/`.
- Coverage: `backend-java/src/test/java/com/goodnews/backendjava/ingestion/application/SyncActiveSourcesTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/ingestion/application/ReloadSourcePostsTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/api/MonitoringControllerContractTest.java`, and `backend-java/src/test/java/com/goodnews/backendjava/ingestion/infrastructure/persistence/R2dbcSourceReloadWriterIT.java`.
- Reviewed implementation basis for this plan update: current `master` bulk-sync and monitoring state after commit `acad841` (`feat: port bulk source sync and monitoring`).

**Exact changes**

- Port bulk source sync with explicit concurrency limits and failure aggregation.
- Port any reload-posts or rescan flows used by the Python backend.
- Port monitoring summary, queue, and analyze-now behaviors from `backend/app/api/routes/monitoring.py` and related services.
- Preserve monitoring-visible outcome data for sync jobs and source status reporting.

**Definition of done**

- Java can run single-source and bulk-source sync safely, expose the related operational state, and support the current Monitoring tab behavior.

**Verification**

- Integration tests for multi-source sync and partial failures.
- Stress-style checks for concurrency caps.
- API integration tests for monitoring summary and queue views.

**Risks/notes**

- Reactive does not mean unlimited concurrency. The concurrency cap and scheduler choices must be explicit in this PR.

### PR-16. Port Analysis Pipeline and Gemini Integration [Completed on master]

**Goal**

Move the analysis subsystem as one testable slice instead of splitting orchestration from transport.

**Status**

- Completed on `master`.
- Artifact: analysis pipeline under `backend-java/src/main/java/com/goodnews/backendjava/analysis/`, including `analysis/application/AnalyzePendingPosts.java`, Gemini integration under `analysis/infrastructure/gemini/`, persistence adapters under `analysis/infrastructure/persistence/`, and config in `backend-java/src/main/java/com/goodnews/backendjava/config/GeminiProperties.java`.
- Coverage: `backend-java/src/test/java/com/goodnews/backendjava/analysis/application/AnalyzePendingPostsTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/analysis/infrastructure/gemini/GeminiAnalysisClientTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/analysis/infrastructure/persistence/AnalysisPipelineIT.java`, and related analysis normalization/configuration tests.
- Reviewed implementation basis for this plan update: current `master` analysis state after commit `81dc596` (`feat: port analysis pipeline and gemini integration`).

**Exact changes**

- Port analysis orchestration, persistence, and result mapping from `backend/app/services/analysis.py` and related models.
- Port the Gemini client from `backend/app/ai/gemini_client.py` using the shared reactive HTTP layer.
- Preserve model selection, request shaping, retries, stub/test behavior, and error translation expected by the current service layer.

**Definition of done**

- Java can execute the analysis pipeline end to end, including Gemini-backed calls and persisted analysis results.

**Verification**

- Unit tests for orchestration and persistence mapping.
- Mocked HTTP client tests for Gemini success, retryable failure, and permanent failure cases.
- Integration tests for the end-to-end analysis flow.

**Risks/notes**

- The earlier split between domain orchestration and Gemini transport was too granular for the real amount of coupling here.

### PR-17. Port Digest Generation, Rendering, and Delivery

**Goal**

Move digest creation and delivery as one complete operational feature.

**Exact changes**

- Port digest generation from `backend/app/services/digest_service.py`.
- Port digest email rendering and template assets for daily and weekly digests.
- Connect digest generation to the SMTP delivery adapter.
- Preserve recipient selection, batching, history linkage, and failure-reporting semantics.
- Keep blocking SMTP work isolated away from the event loop.

**Definition of done**

- Java can generate, render, and send daily and weekly digests end to end with behavior compatible enough for production soak use.

**Verification**

- Integration tests for generated digest contents and persistence.
- Snapshot-style tests for rendered email output.
- Mock-SMTP end-to-end tests covering generation plus send.

**Risks/notes**

- Digest generation and delivery are tightly coupled at the operational level, so separating them created more planning overhead than safety.

### PR-18. Port Internal Job Endpoints and Scheduler Behavior

**Goal**

Reach backend parity for the current scheduled automation surface.

**Exact changes**

- Port `/internal/jobs/source-sync`.
- Port all branches behind `/internal/jobs/digests`, including:
  - daily digest
  - weekly digest
  - daily observability report
- Apply the scheduler invoker auth model from the security phase.
- Preserve current trigger semantics, branching behavior, and scheduler-facing response contracts.

**Definition of done**

- Cloud Scheduler can invoke the Java backend for the full current internal-jobs surface with equivalent behavior.

**Verification**

- Integration tests for authorized and unauthorized invocations.
- Controlled end-to-end runs for source sync, daily digest, weekly digest, and observability-report paths.

**Risks/notes**

- This is the minimum useful unit for scheduler parity. Splitting the digest branches further created too much PR overhead relative to the code movement.

### PR-19. Add Shared Frontend Backend Targeting and Global Selector

**Goal**

Create one frontend-level switch that can move every page between Python and Java while both backends share the same database.

**Exact changes**

- Update `frontend/src/lib/api.ts` so the frontend can resolve both:
  - Python backend origin
  - Java backend origin
- Keep request routing centralized in shared API wiring.
- Add shared runtime backend-target state that switches all frontend requests together.
- Make backend-target changes trigger full UI retargeting so already-open pages refetch from the newly selected backend.
- Update `frontend/src/app/AppShell.tsx`, where the header currently renders three top summary cards.
- Add the backend selector as the fourth header block visible on every page.
- Persist the selected target in a simple, explicit way suitable for debugging and side-by-side validation.
- Keep the selector scoped as an internal/staging/controlled migration tool rather than a permanent end-user feature.

**Definition of done**

- The frontend has one global backend-target abstraction and one global selector that reroutes all page traffic between Python and Java without page-specific wiring.

**Verification**

- Frontend tests for API-root selection, request routing, selector rendering, persistence, and full-app retargeting after target changes.
- Manual smoke checks across Feed, Sources, Preferences, Settings, Digests, Want To Read, and Monitoring.

**Risks/notes**

- Per-page backend switching would be a bad design here because it creates permanent drift and partial-stale-data bugs.

### PR-20. Add Dual-Backend Local Validation and Python-vs-Java Contract Harness

**Goal**

Make the parallel-run period testable rather than trust-based.

**Exact changes**

- Add local smoke scripts and workflow docs so one frontend can be run against Python and Java in parallel.
- Document the repo-specific dual-backend workflow with one shared database.
- Add automated contract tests that run representative API calls against both backends on the same dataset for:
  - posts
  - feedback
  - preferences
  - settings
  - sources
  - digests
  - monitoring
- Compare status, response shape, ordering-sensitive fields, and key business values.
- Include explicit checks that both backends accept the same frontend origins and Firebase-authenticated browser requests while selector switching is enabled.

**Definition of done**

- Developers can validate both backends locally and CI can detect meaningful contract drift during the parallel-run window.

**Verification**

- Smoke run against both local backends through the selector.
- Contract-suite execution with at least one intentional mismatch to prove failures are actionable.

**Risks/notes**

- This is not test polish. Without it, the selector and shared-database strategy are much riskier than they look.

### PR-21. Add Java Build, Migration, and Non-Production Deploy Pipeline

**Goal**

Make `backend-java` fully buildable, migratable, and deployable before shared-environment validation begins.

**Exact changes**

- Extend GitHub Actions so `backend-java` can:
  - build a Java image
  - push it to Artifact Registry
  - execute Flyway migrations in the deploy path
  - deploy a separate non-production Cloud Run service
- Wire env and secret handling for:
  - database URL
  - app master key
  - Gemini API key
  - Firebase project id
  - allowed emails
  - scheduler invoker
  - public origins
- Preserve the existing Python production deploy path during the parallel-run window.

**Definition of done**

- GitHub Actions can build, publish, migrate, and deploy `backend-java` to a separate non-production Cloud Run target without affecting the active Python production service.

**Verification**

- Successful workflow run for image build and push.
- Successful workflow run for Flyway execution against a non-production database.
- Successful workflow run that deploys the Java service and passes `/api/health` smoke checks.

**Risks/notes**

- Splitting build, migrate, and deploy into separate future PRs created too much process overhead for one operational concern.

### PR-22. Stand Up Full Staging Parallel-Run Validation

**Goal**

Prove the dual-backend design in a shared environment before any production exposure.

**Exact changes**

- Deploy the Java backend to staging.
- Add a staging frontend path whose shared selector can target either staging backend.
- Configure both staging backends to accept the same staging frontend origin set and the same Firebase-authenticated browser request pattern.
- Expose the selector in staging for internal validation.
- Point staging scheduler jobs at Java internal-job endpoints after backend and frontend staging paths are proven.
- Keep rollback instructions explicit for staging backend, frontend, and scheduler changes.

**Definition of done**

- Staging runs one frontend with a global selector and two backends against the same staging database, and staged scheduler automation can run through Java.

**Verification**

- End-to-end smoke of Feed, Sources sync, Preferences recompute, Settings test email, Digest history, Monitoring, and internal jobs in staging against the Java target.
- Manual selector-retargeting checks between staging Python and staging Java backends.

**Risks/notes**

- This phase is intentionally larger because splitting staging backend, staging frontend, and staging scheduler created overhead without much risk reduction.

### PR-23. Roll Out Production Frontend Selector and Switch Default to Java

**Goal**

Use the shared selector model to shift production browser traffic to Java in a controlled way.

**Exact changes**

- Deploy the selector-enabled frontend to production with both backend origins configured.
- Keep Python as the initial default for a controlled validation window.
- Gate selector usage for internal/support/controlled migration validation rather than presenting it as a normal end-user feature.
- After the soak window, switch the production frontend default target from Python to Java.
- Keep Python available for controlled rollback validation until the parallel-run window closes.

**Definition of done**

- Production frontend can route to both backends during validation, and then defaults to Java once browser-flow parity is proven.

**Verification**

- Controlled production smoke checks against both selector targets.
- Business-flow smoke checks after Java becomes the default target.
- Monitoring for error-rate, latency, and data-consistency regressions while both backends remain active.

**Risks/notes**

- The all-or-nothing per-session selector is actually a safer production migration tool than trying to split traffic route by route inside one UI session.

### PR-24. Shift Production Scheduler and Digest Operations to Java

**Goal**

Complete the production ownership transfer after browser traffic is already stable on Java.

**Exact changes**

- Point production Cloud Scheduler jobs at the Java backend.
- Move source sync, digest generation, digest delivery, and observability-report execution ownership to Java.
- Confirm Cloud Run service accounts, OIDC audience, secrets, and operational dashboards are correct on the Java side.

**Definition of done**

- Automated production behavior runs through Java rather than Python.

**Verification**

- Successful controlled runs of source sync, daily digest, weekly digest, and observability-report paths in production.
- Delivery confirmation for a controlled digest cycle.

**Risks/notes**

- This is the most operationally sensitive production cutover, so it should happen only after the browser-facing slice is already stable.

### PR-25. Retire Python Backend from the Active Production Path

**Goal**

Finish the migration and make Java the sole active production backend.

**Exact changes**

- Remove the Python backend from the active Cloud Run production path after the Java soak window.
- Update CI/CD, deploy workflows, and operational docs to make Java the primary backend.
- Keep rollback/archive strategy explicit according to team policy.

**Definition of done**

- Java is the sole active production backend path and repo automation reflects that reality.

**Verification**

- Full regression smoke.
- Review of CI, deploy workflows, and README for consistency with the final architecture.

**Risks/notes**

- Do not rush this phase. Python should remain available until Java has earned operational trust across both browser and scheduled workloads.

## Per-PR Working Rules

- Every implementation PR starts on a dedicated branch, not on `master`.
- Every PR includes only one phase's scope plus any minimal supporting tests/docs required to keep the repo healthy.
- Every PR ends with relevant verification run locally and in CI. For Java backend work, PR-03 establishes the dedicated GitHub Actions coverage that all later Java phases are expected to use; PR-02 is the only bootstrap exception and should merge immediately before PR-03.
- Every PR gets review focused on correctness, contract compatibility, and reactive-stack discipline.
- No PR should defer critical behavior with comments like "wire later" when that behavior is already part of the live Python backend contract.
- Frontend backend-target work stays centralized in shared wiring such as `frontend/src/lib/api.ts` and `frontend/src/app/AppShell.tsx`; do not split that migration into separate per-page implementations.
