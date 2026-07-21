# Reactive Java Backend Migration Plan

## Principles and Constraints

- Target stack: Java 21, Spring Boot 3, WebFlux, Reactor, Maven, R2DBC, Flyway.
- Migration is incremental. The current FastAPI backend in `backend/` stays operational until Java takes over each contract.
- Each phase must be independently verifiable and reversible, end in one merged PR, and leave the repo in a working state.
- Runtime paths must stay fully reactive: WebFlux controllers, Reactor services, R2DBC persistence, WebClient for HTTP integrations. Do not introduce JPA or JDBC into request-processing code.
- Existing backend behavior is the source of truth at first: keep current API shapes, auth rules, DB semantics, scheduler entrypoints, and operational topology before attempting cleanup.
- Existing deployment model matters: production today is a FastAPI monolith on Cloud Run, migrations run through a Cloud Run job, CI is in `.github/workflows/ci.yml`, and deploy is in `.github/workflows/deploy.yml`. The repo still contains legacy split-service runtimes and tests such as `source_ingestion_service`, `analysis_llm_service`, `delivery_service`, and `content_api_service`; those traces must be inventoried explicitly instead of being mistaken for the active production topology.
- Keep the new backend in a separate module such as `backend-java/` until cutover is complete.
- During the parallel-run window, Python and Java must both be able to operate against the same source-of-truth database. Their DB schema expectations, persisted-data semantics, auth behavior, CORS/public-origin handling, and frontend-visible API contracts must remain compatible for as long as parallel operation exists.
- Production browser migration follows a strangler model: one centralized operation-ownership map decides whether each frontend API operation calls Python or Java. Backend ownership must never be wired page by page or exposed as a production end-user selector.
- A whole-app Python/Java selector may exist only in local, preview, or staging environments as a diagnostic tool. Production ownership changes are versioned deployment decisions with an explicit rollback path.
- Schema changes during coexistence follow expand-and-contract rules. Exactly one migration system owns production schema changes at a time, and destructive contract migrations wait until Python has left the rollback path.
- Side-effecting background capabilities such as source sync, analysis, digest delivery, and scheduler jobs have exactly one production owner at a time. Shared database access is not permission to run both implementations concurrently.
- Deploy Java code before routing production traffic to it. Every production ownership change must be independently reversible without requiring a database rollback.
- Cloud Run, Firebase Auth, Gemini, Gmail SMTP, Secret Manager, and Neon Postgres all need explicit migration steps. None of them should be treated as "will wire later".
- Blocking libraries may still exist at the edges, especially SMTP, HTML parsing, and some crypto operations. If blocking code cannot be avoided, isolate it explicitly away from the Netty event loop and document the scheduler choice in the PR.

## PR Phases

### PR-01. Freeze Migration Scope and Current Contracts [Completed on master]

**Goal**

Create a single source of truth for what the Java backend must replace.

**Status**

- Completed on `master`.
- Artifact and reviewed source: `docs/reactive-java-backend-pr-01-inventory.md`.

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

### PR-17. Port Digest Generation, Rendering, and Delivery [Completed on master]

**Goal**

Move digest creation and delivery as one complete operational feature.

**Status**

- Completed on `master`.
- Artifact: digest generation and delivery under `backend-java/src/main/java/com/goodnews/backendjava/digest/`, including `DigestGenerationService.java`, `DigestEmailRenderer.java`, `DigestDeliveryService.java`, `DigestRepository.java`, `DeliveryObservability.java`, and supporting digest models.
- Artifact: schema support in `backend-java/src/main/resources/db/migration/V5__unique_digest_run_slots.sql`.
- Coverage: `backend-java/src/test/java/com/goodnews/backendjava/digest/DigestGenerationServiceTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/digest/DigestEmailRendererTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/digest/DigestDeliveryIT.java`, and `backend-java/src/test/java/com/goodnews/backendjava/digest/DeliveryObservabilityTest.java`.
- Reviewed implementation basis for this plan update: current `origin/master` head commit `c68c556` (`feat: port digest generation and delivery`).

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

### PR-18. Port Internal Job Endpoints and Scheduler Behavior [Completed on master]

**Goal**

Reach backend parity for the current scheduled automation surface.

**Status**

- Completed on `master`.
- Artifact: scheduler-facing endpoints in `backend-java/src/main/java/com/goodnews/backendjava/api/InternalJobsController.java`.
- Artifact: source sync and digest scheduling behavior in `backend-java/src/main/java/com/goodnews/backendjava/jobs/SourceSyncJob.java` and `backend-java/src/main/java/com/goodnews/backendjava/jobs/ScheduledDigestJobs.java`.
- Artifact: daily observability report generation and delivery in `backend-java/src/main/java/com/goodnews/backendjava/digest/ObservabilityReportGenerator.java` and `backend-java/src/main/java/com/goodnews/backendjava/digest/DigestDeliveryService.java`.
- Coverage: `backend-java/src/test/java/com/goodnews/backendjava/api/InternalJobsControllerContractTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/jobs/SourceSyncJobTest.java`, `backend-java/src/test/java/com/goodnews/backendjava/jobs/ScheduledDigestJobsTest.java`, and `backend-java/src/test/java/com/goodnews/backendjava/security/ReactiveSecurityIntegrationTest.java`.
- Reviewed implementation basis for this plan update: `origin/master` commit `6c2da18` (`feat: port internal scheduler jobs`); CI, CodeQL, and deploy workflows completed successfully.

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

## Production Strangler Topology

The completed phases above mean that the corresponding Java implementation has landed on `master`; they do not by themselves mean that the capability is proven in staging or owns production traffic. The remaining phases distinguish four levels of confidence: implemented, contract-verified, staging-proven, and production-proven.

During production coexistence:

- `good-news-app` remains the Python Cloud Run service and the default owner at the start.
- A separate `good-news-java` Cloud Run service runs the Java backend against the same Neon PostgreSQL database.
- `frontend/src/lib/api.ts` contains one versioned operation-ownership map. Every frontend API function resolves its origin through this map; pages never choose origins themselves.
- Production has no user-selectable backend switch. Local, preview, and staging builds may expose a whole-app selector for diagnostics.
- Each backend adds an `X-Good-News-Backend: python|java` response header so production routing and logs are auditable.
- Browser routing initially happens in the shared frontend API layer because it can distinguish operations that share a path but use different HTTP methods. A common ingress may replace this later, but it is not required for the first slices.
- Direct callers that do not go through the frontend, including email feedback links and Cloud Scheduler, have their ownership changed explicitly in the phase that migrates them.
- Firebase Hosting rewrites may be used for short path-based routes, but not as the only ingress for long-running sync or job requests.
- Native Cloud Run percentage-based revision traffic splitting is not used to divide Python and Java ownership because both revisions would need to implement every routed contract.

The first production browser ownership map is intentionally mixed:

| Operation | Initial production owner | First migration target |
| --- | --- | --- |
| Feed reads | Python | Java after reaction interoperability is proven |
| Feedback, want-to-read, read-later, and open actions | Python | Java first |
| Preferences and settings | Python | Java after feed stability |
| Source management and ingestion | Python | Java only as a coherent capability |
| Digest history reads | Python | Java as a read-model slice |
| Digest generation and delivery | Python | Java during exclusive background cutover |
| Cloud Scheduler jobs | Python | Java last |
| Production schema migrations | Alembic | Flyway before Java receives business traffic |

Every production ownership PR records its exact before/after operation map, rollback command or deployment action, soak start and end, minimum observation sample, and route-specific error-rate and latency thresholds derived from the Python baseline. A switch cannot close on manual smoke alone: its contract suite must be green, unexpected `5xx` responses must be explained, database connections must remain within the shared budget, and rollback must have been exercised in the same environment class.

### PR-19. Establish the Production Strangler Foundation and Close Parity Gaps

**Goal**

Create a reversible per-operation routing foundation without changing production ownership yet, and close runtime gaps that would otherwise block the first Java request.

**Exact changes**

- Update `frontend/src/lib/api.ts` to resolve both Python and Java origins through one operation-ownership map.
- Keep every production operation assigned to Python in this phase so the frontend change is behavior-preserving.
- Fail the frontend build or tests when an exported API operation has no explicit owner.
- Do not add a production backend selector. Allow an optional whole-app override only in local, preview, and staging builds.
- Add `X-Good-News-Backend` response headers to both backends.
- Add Java CORS behavior compatible with the active Python frontend-origin and Authorization-header contract, including preflight tests.
- Restore `/api/health` parity: Java must return the public Python response shape and return `503` when the database or required schema is not ready.
- Stop exposing Prometheus metrics as an unauthenticated public operations endpoint; use a protected management path or the chosen Cloud Monitoring integration.
- Add or verify request correlation, route-level latency/error metrics, structured logs, and backend identity dimensions.
- Add an explicit R2DBC connection pool and size it against the combined Python-plus-Java Neon connection budget.
- Add bounded connection and operation timeouts for PostgreSQL and SMTP edges.
- Review the Java dependency baseline and production JVM settings before the first Cloud Run deployment.

**Definition of done**

- The production frontend contains centralized operation routing but still sends all requests to Python.
- Java passes health, auth, CORS, connection-budget, and management-endpoint readiness checks required for a production shadow deployment.
- Reverting the frontend routing configuration restores the previous single-origin behavior without a database change.

**Verification**

- Frontend tests for complete routing-map coverage and the all-Python default.
- Java integration tests for `/api/health` success and failure semantics.
- Browser preflight and Firebase-authenticated request tests against both origins.
- Tests that the backend identity header is present and Prometheus is not publicly exposed unintentionally.
- Connection-pool saturation and timeout smoke tests.

**Risks/notes**

- The operation map is a migration control plane, not a general feature-flag framework.
- A hidden production selector is not an access-control mechanism and must not replace versioned ownership changes.

### PR-20. Build a Differential Contract and Persisted-State Harness

**Goal**

Make each production ownership decision evidence-based without allowing one backend's mutation to contaminate the other backend's expected result.

**Exact changes**

- Add local orchestration for Python, Java, and isolated PostgreSQL test databases.
- Seed two identical database copies for mutation scenarios:
  - Python executes against database A.
  - Java executes against database B.
- Compare for every active route group:
  - status and error class
  - JSON shape and meaningful values
  - ordering and pagination
  - redirects and public URLs
  - final persisted table state
- Normalize only documented volatile values such as generated ids, timestamps, and correlation ids.
- Use identical fake clocks and deterministic fixtures.
- Record and compare SMTP, Gemini, and source-fetch side effects through shared test adapters rather than calling real external systems in CI.
- Cover Firebase authentication, allowed-email behavior, scheduler OIDC behavior, CORS preflight, validation failures, not-found cases, retries, and idempotency.
- Add a smaller read-only smoke mode that can run both backends against one shared database without mutating it.
- Publish a route-by-route parity report that becomes the go/no-go input for later production switches.

**Definition of done**

- CI detects HTTP or persisted-state drift without depending on sequential writes to one shared dataset.
- The reaction slice planned for PR-23 has complete success, failure, idempotency, and cross-backend read-after-write coverage.

**Verification**

- Run the harness with all comparisons green.
- Introduce and restore one HTTP mismatch and one persisted-state mismatch to prove diagnostics identify the owning route and differing field or row.
- Run the shared-database read-only mode against both local backends.

**Risks/notes**

- Running mutating differential tests sequentially against one database creates both false positives and false negatives and is prohibited.
- Contract equality includes side effects and persisted semantics, not only response JSON.

### PR-21. Transfer Production Database Migration Ownership from Alembic to Flyway

**Goal**

Move schema-migration ownership to Java while Python still serves all production application traffic, making the database transition independently observable and reversible at the application layer.

**Exact changes**

- Freeze the Alembic chain at its current head and document that no new production schema changes may be added through Alembic after this phase.
- Add an explicit Alembic-head-to-Flyway-baseline bridge:
  - assert the exact expected tables, columns, constraints, indexes, and Alembic revision
  - create a Flyway baseline at version 4 only after those assertions pass
  - apply V5 and later Flyway migrations normally
- Keep `alembic_version` in place for the entire Python rollback window.
- Add upgrade tests that start from a real Alembic-head schema containing representative existing data, not only from an empty Flyway-created database.
- Continue testing clean-database creation through Flyway V1..latest.
- Build and publish the migration-capable Java image needed by the dedicated job without deploying the Java serving service yet.
- Run Flyway through a dedicated Cloud Run migration job with a shared PostgreSQL advisory-lock contract.
- Disable automatic Flyway migration in the serving Java Cloud Run service.
- Update the deploy workflow so the dedicated Flyway job is the sole production schema writer.
- Make all migrations during coexistence backward compatible with the running Python version:
  - add nullable columns or compatible defaults first
  - backfill separately when needed
  - do not rename or drop Python-visible objects
- Rehearse database backup, restore, baseline, and migration on a production-like copy before touching production.
- Apply the baseline and V5 in production while all API and scheduler traffic still belongs to Python.

**Definition of done**

- Production schema history is owned by Flyway and Python continues to operate normally against the migrated schema.
- A failed Java application rollout can be reverted to Python without rolling the schema back.
- Both clean installs and Alembic-origin upgrades are covered in CI.

**Verification**

- Automated empty-database Flyway migration test.
- Automated Alembic-head-to-Flyway-latest upgrade test with row-count and representative-value assertions.
- Backup/restore rehearsal on a non-production copy.
- Production migration-job run followed by Python API, scheduler, and health smoke checks.
- Confirm that a second migration invocation is safe and makes no changes.

**Risks/notes**

- Do not enable blind `baselineOnMigrate`; a mismatched non-empty schema must fail rather than be silently accepted.
- Do not run Alembic and Flyway as competing production migration writers.
- Destructive contract migrations belong after PR-27 and after the rollback window closes.

### PR-22. Build, Deploy, and Observe Java as a Production Shadow

**Goal**

Deploy the real Java artifact through staging and into production with zero normal user or scheduler traffic.

**Exact changes**

- Extend GitHub Actions so `backend-java` can:
  - build a reproducible Java image
  - run tests and dependency/security checks
  - push the image to Artifact Registry
  - deploy a dedicated staging service
  - deploy `good-news-java` as a separate production Cloud Run service
- Keep the dedicated Flyway job from PR-21 separate from the serving image startup lifecycle.
- Wire and validate environment and secret handling for database, master key, Gemini, Firebase, allowed emails, scheduler identity, and public origins.
- Set explicit Cloud Run CPU, memory, request concurrency, timeout, min/max instances, startup probe, and connection-budget values.
- Update dashboards and alerts so Python and Java request counts, error rates, latency, startup latency, memory, database saturation, and external-call failures are distinguishable.
- Use a staging or preview frontend selector for whole-app diagnostic testing only.
- Run the differential suite and end-to-end staging flows before production shadow deployment.
- In production, allow only controlled direct smoke requests to the Java URL; keep the operation-ownership map fully on Python.

**Definition of done**

- The exact Java image intended for production is healthy in staging and deployed to production without owning normal traffic.
- Java startup never mutates the schema and its resource usage is visible before routing a business capability.
- Python deploy and rollback behavior remains unchanged.

**Verification**

- Successful image build, push, staging deploy, production shadow deploy, and health smoke.
- Full staging flow for Feed, reactions, Sources, Preferences, Settings, Digests, Monitoring, and internal jobs.
- Controlled Java production reads against the shared production database.
- Cold-start, connection-pool, and representative latency measurements compared with the Python baseline.

**Risks/notes**

- Deploying code and routing traffic are separate events. A successful deploy is not authorization to change ownership.
- Production secrets and external integrations should be enabled only to the degree needed for the controlled smoke; background jobs remain disabled.

### PR-23. Move Production Reaction Flows to Java

**Goal**

Prove real Python/Java interoperability by letting Java persist user reactions while Python continues to serve the feed that reads them.

**Exact changes**

- Change the production operation-ownership map to route these browser operations to Java:
  - `PUT /api/feedback/{post_id}`
  - `PUT /api/want-to-read/{post_id}`
  - `POST /api/posts/{post_id}/read-later`
  - `POST /api/posts/{post_id}/open`
- Keep `GET /api/posts` on Python for the entire phase.
- Decide the non-browser entrypoint for `GET /api/feedback/{post_id}/{state}`:
  - route newly generated email links to Java through an explicit public origin, or
  - keep the link endpoint on Python until a common ingress exists
- Keep existing Python email links valid throughout the rollback window.
- Verify that a Java write is committed before its response completes and is immediately visible to a subsequent Python feed read.
- Add production dashboards and alerts specifically for reaction write errors, conflicts, and read-after-write mismatches.
- Document and rehearse rollback as an ownership-map change back to Python without a schema rollback.

**Definition of done**

- Production reactions are written by Java and reflected correctly in the Python-served feed.
- Duplicate and concurrent reaction requests preserve the existing idempotency and final-state rules.
- The slice can return to Python independently of every other route group.

**Verification**

- Controlled production flows for each reaction operation followed by Python feed reads.
- Repeated and concurrent update tests.
- Firebase-authenticated browser checks and CORS preflight checks.
- Observe a defined soak window with no unexplained parity, error-rate, or latency regression before PR-24.

**Risks/notes**

- This phase deliberately mixes Python reads and Java writes; that is the behavior being proven, not a temporary test accident.
- Direct email links do not use the frontend routing map and must retain an explicit owner.

### PR-24. Move Feed and Safe Read Models to Java

**Goal**

Move the highest-volume browser reads after Java writes have already proven compatible with Python reads.

**Exact changes**

- Route `GET /api/posts` to Java, including all filters, sorting, pagination, enrichment, and read-later behavior.
- Route digest history list/detail reads to Java while digest generation may still be owned by Python.
- Route monitoring summary and queue reads to Java when their database semantics pass the differential harness.
- Route source list reads only if doing so does not obscure Python-owned onboarding state.
- Keep preferences, settings, source mutations, sync/reload, analyze-now, and all internal jobs on Python.
- Add route-specific performance gates using the established Python baseline rather than arbitrary absolute targets.
- Keep rollback at operation granularity.

**Definition of done**

- Feed and selected read models are production-proven on Java while Python remains available as a route-level fallback.
- Response ordering, pagination, and user-visible state remain contract-compatible.

**Verification**

- Differential suite for every migrated query combination.
- Production smoke across Feed, Want To Read, Digests, and Monitoring.
- Compare Java and Python p50/p95 latency, error rate, database connections, and memory during the soak window.
- Roll one read operation back to Python and restore it to Java to verify the control path.

**Risks/notes**

- Read-only routing is still capable of causing user-visible drift through ordering, defaults, null handling, and time-window interpretation.
- Do not route long-running mutations through Firebase Hosting merely to obtain a common origin because Hosting has a shorter request timeout than the active Cloud Run service contract.

### PR-25. Move Preferences, Settings, and Interactive Source Management

**Goal**

Complete browser-facing ownership while preserving source onboarding and external-side-effect semantics.

**Exact changes**

- Move preferences read and recompute together.
- Move settings read, update, and test-email together, including encryption compatibility and bounded SMTP timeout behavior.
- Before routing source creation to Java, close the remaining onboarding parity gap:
  - source creation must trigger discovery and initial sync with the existing user-visible semantics
  - onboarding progress needed by `/api/sources/{source_id}/log` must survive instance changes or be represented by persisted state
  - source status transitions and failure details must remain compatible
- Treat source create, onboarding, onboarding log, and initial sync as one capability rather than independent endpoints.
- Add a per-source execution lease or advisory-lock contract before allowing Java manual sync/reload to coexist with Python-owned bulk scheduling.
- Route interactive source list, create, update, delete, single sync, and reload operations only after the capability passes the harness.
- Keep scheduled bulk sync, automated analysis, digest delivery, and internal jobs on Python.

**Definition of done**

- Every interactive frontend page is owned by Java, with Python retained as a route-level rollback target.
- Source onboarding does not depend on hitting the same in-memory process for follow-up log requests.
- Manual source operations cannot overlap unsafely with Python scheduler work.

**Verification**

- Production smoke for Preferences, Settings, test email, Sources CRUD, onboarding/log polling, single sync, and reload.
- Instance-restart test during source onboarding.
- Cross-runtime source-lock contention test.
- Fixed-vector secret compatibility and controlled SMTP delivery verification.
- Defined browser-traffic soak before background ownership changes.

**Risks/notes**

- The current Python source onboarding log is process-local, so shared PostgreSQL alone is not sufficient for a split owner design.
- Do not move `POST /api/sources` independently from its onboarding and log behavior.

### PR-26. Move Background Processing and Scheduler Ownership Exclusively to Java

**Goal**

Transfer all automated and externally side-effecting work without allowing Python and Java to execute the same logical run concurrently.

**Exact changes**

- Add a shared persisted job-run or advisory-lock ownership contract covering:
  - bulk source sync
  - pending analysis
  - daily digest
  - weekly digest
  - daily observability report
- Include logical run keys, owner identity, start/finish state, retry handling, and stale-lease recovery where applicable.
- Prove that concurrent and retried Python/Java invocations cannot duplicate a logical job or email delivery.
- Transfer production ownership in controlled substeps:
  1. disable the Python target for one job
  2. wait for any in-flight Python execution to finish or expire safely
  3. invoke the Java path manually
  4. verify persisted state and external effects
  5. repoint and enable the Cloud Scheduler job
- Move Gemini-backed analysis ownership before moving digest generation that depends on analysis results.
- Move source sync, analysis, daily digest, weekly digest, and observability report independently; do not combine their go/no-go decisions merely because they share one endpoint today.
- Update Cloud Scheduler OIDC audience, service account permissions, timeouts, retry policy, and dashboards for the Java target.
- Keep a symmetric per-job rollback runbook that disables Java ownership before re-enabling Python.

**Definition of done**

- Java has exclusive production ownership of all scheduled and background capabilities.
- Retried or overlapping requests cannot cause duplicate logical runs or duplicate digest delivery.
- Python remains deployable for rollback but has no enabled scheduler ownership.

**Verification**

- Concurrent and retry tests for every logical job key.
- Controlled production runs for source sync, analysis, daily digest, weekly digest, and observability report.
- Delivery confirmation and persisted-state inspection for controlled digest cycles.
- Exercise one per-job rollback and restoration before closing the phase.

**Risks/notes**

- A shared database does not provide exclusive job ownership unless the ownership rule is encoded and tested.
- Scheduler target updates are not instantaneous; the handoff runbook must account for in-flight requests.

### PR-27. Complete the Java Soak and Retire Python from the Active Path

**Goal**

Close the strangler migration after Java has proven browser and background ownership independently.

**Exact changes**

- Confirm the operation-ownership map assigns all active browser operations to Java.
- Keep Python deployed with zero normal traffic and all schedulers disabled for a defined rollback window.
- Define exit gates from observed production baselines, including:
  - route-level error rate
  - p95 latency and cold-start behavior
  - database connection saturation
  - source-sync and analysis success rates
  - absence of duplicate digest delivery
  - successful daily, weekly, and observability job cycles
  - demonstrated rollback within the agreed recovery time
- After the rollback window closes:
  - remove Python from the active Cloud Run and frontend routing path
  - remove Alembic execution from deployment automation while retaining migration history as archival evidence
  - make Java the sole backend build, migration, deploy, and scheduler target
  - remove obsolete Python secrets, IAM grants, service URLs, dashboards, and alerts
  - update README, runbooks, and architecture documentation
- Archive or delete legacy split-service runtime code according to repository policy only after confirming it is not part of the rollback package.
- Plan destructive Flyway contract migrations as later cleanup work, not as part of the cutover itself.

**Definition of done**

- Java is the sole active production backend, schema migrator, and background-job owner.
- The repository automation and operational documentation reflect the final architecture.
- Python can no longer receive accidental production traffic or scheduled invocations.

**Verification**

- Full production regression smoke.
- Review frontend routing, Cloud Run services, Scheduler targets, CI/CD, Secret Manager, IAM, monitoring, and README for stale Python references.
- Restore rehearsal from the final pre-retirement database backup.
- Confirm that clean-environment deployment through Flyway and Java succeeds without Alembic or Python runtime dependencies.

**Risks/notes**

- Do not combine retirement with destructive schema cleanup; retaining an expand-only schema for one additional release preserves recovery options.
- Zero routed traffic is not proof of retirement until direct URLs, schedulers, deploy workflows, and credentials are also removed or disabled.

## Per-PR Working Rules

- Every implementation PR starts on a dedicated branch, not on `master`.
- Every PR includes only one phase's scope plus any minimal supporting tests/docs required to keep the repo healthy.
- Every PR ends with relevant verification run locally and in CI. For Java backend work, PR-03 establishes the dedicated GitHub Actions coverage that all later Java phases are expected to use; PR-02 is the only bootstrap exception and should merge immediately before PR-03.
- Every PR gets review focused on correctness, contract compatibility, and reactive-stack discipline.
- No PR should defer critical behavior with comments like "wire later" when that behavior is already part of the live Python backend contract.
- Frontend production ownership stays centralized in the operation map in `frontend/src/lib/api.ts`; do not add page-specific origins or a production end-user selector.
- Every production capability switch deploys and verifies the target first, changes ownership second, observes a defined soak window, and preserves an independently tested rollback.
- Mutating differential tests use isolated, identically seeded databases. Shared-database comparison is limited to read-only smoke and explicit cross-runtime interoperability scenarios.
- Alembic and Flyway never compete as production schema writers, and Python and Java never concurrently own the same scheduled side effect.
