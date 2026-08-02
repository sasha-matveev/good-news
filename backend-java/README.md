# Good News reactive Java backend

The module targets Java 21 and Spring Boot 3.5.16. It is deployed as a regular
production backend; browser operation ownership is controlled independently by
the frontend operation map during the strangler migration.

## Maven modules

- `backend` is a regular library containing the API, application services, and
  infrastructure shared by executable applications. It has no `main` class.
- `application` produces the serving binary whose entry point is
  `GoodNewsApplication`.
- `migration` owns Flyway SQL and produces the one-shot migration binary whose
  entry point is `MigrationApplication`.
- `contract` produces the deterministic API-parity binary with its test
  boundary adapters. Contract-only code is not copied into the serving build.
- `verification` contains the shared unit and integration suites that assemble
  the serving application with migration test fixtures. It is not executable
  and is the only module that depends on both binaries.

The serving and migration lifecycles are selected by choosing a binary, not by
passing a mode flag to a shared application.

## Production readiness contract

- `GET /api/health` is public and returns `{"status":"ok"}` only when the
  database has the required schema. Database or schema failure
  returns `503` with `{"status":"error","reason":"database or required schema is not ready"}`.
- Every response carries `X-Good-News-Backend: java` and `X-Correlation-ID`.
- CORS permits the configured `GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN` plus the local
  Vite origins. Authorization, content type, and correlation headers are
  accepted in browser preflight requests.

## Authentication and CSRF threat model

The service uses request-scoped bearer authentication and does not persist a
Spring Security context in a browser session:

- `/api/**`, except the public `/api/health`, requires a Firebase ID token in
  the `Authorization: Bearer` header when Firebase authentication is configured.
  An unconfigured local-development instance treats these routes as anonymous
  and grants no user identity.
- `/internal/jobs/**` requires a Google OIDC token in the `Authorization: Bearer`
  header and verifies the configured scheduler service-account email.
- HTTP Basic and form login are disabled. Cookies are never read as credentials,
  the security context is not stored in a web session, and request caching is
  disabled.

CSRF protection is required for every unsafe request that carries browser
cookies without an explicit bearer token. This makes a cross-origin cookie-only
mutation fail before application code runs while preserving the stateless
Firebase and scheduler bearer flows. New state-changing endpoints must live
under an authenticated route above or be explicitly reviewed and documented as
public.

Adding cookie-backed or session-backed authentication changes this threat
model. Such a change must replace the current matcher with CSRF protection
appropriate to that browser flow and add tests covering token issuance,
submission, and rejection.

## Database connection budget and timeouts

The Java service uses an explicit R2DBC pool. Defaults are deliberately small
for the parallel deployment period:

| Setting | Default |
| --- | --- |
| `GOOD_NEWS_DATABASE_POOL_INITIAL_SIZE` | `0` |
| `GOOD_NEWS_DATABASE_POOL_MAX_SIZE` | `5` |
| `GOOD_NEWS_DATABASE_POOL_ACQUIRE_TIMEOUT` | `2s` |
| `GOOD_NEWS_DATABASE_CONNECT_TIMEOUT` | `5s` |
| `GOOD_NEWS_DATABASE_OPERATION_TIMEOUT` | `30s` |
| `GOOD_NEWS_DATABASE_POOL_IDLE_TIMEOUT` | `10m` |
| `GOOD_NEWS_DATABASE_POOL_MAX_LIFE_TIME` | `30m` |

Python currently uses SQLAlchemy's default `5` pooled plus `10` overflow
connections. With both Cloud Run services capped at one instance, the maximum
application budget is therefore `15 + 5 = 20` connections, excluding migration
and operator reserve. Before either service's instance cap or pool size changes,
check this invariant against the active Neon limit:

```text
(15 × Python max instances) + (Java pool max × Java max instances) + reserve
<= Neon connection limit
```

R2DBC validates borrowed connections with `SELECT 1`; connection creation,
pool acquisition, SQL statements, idle lifetime, and total lifetime are all
bounded. SMTP connect/read/write defaults are `10s`/`30s`/`30s` and can be
overridden with `GOOD_NEWS_SMTP_CONNECTION_TIMEOUT`,
`GOOD_NEWS_SMTP_READ_TIMEOUT`, and `GOOD_NEWS_SMTP_WRITE_TIMEOUT`.

## Cloud Run JVM baseline

The first Java deployment should retain one CPU, `512Mi` memory, a single
maximum instance, and the pool defaults above. Use this reviewed baseline:

```text
JAVA_TOOL_OPTIONS=-XX:InitialRAMPercentage=25 -XX:MaxRAMPercentage=75 -XX:MaxDirectMemorySize=128m -XX:+ExitOnOutOfMemoryError
```

The deployment PR must set the service's request concurrency and timeout
explicitly and load-test them before raising either. The 75% heap ceiling leaves
room inside the container for Netty direct buffers, thread stacks, class
metadata, and native libraries; `ExitOnOutOfMemoryError` lets Cloud Run replace
an unhealthy instance.

## Database migrations

Flyway SQL migrations live in
`migration/src/main/resources/db/migration`. The serving module has no
dependency on the migration module and cannot run them. Invoke the dedicated
migration binary with:

```shell
java -jar /app/good-news-migration.jar
```

The runner uses the existing `good-news.database.*` properties, takes the same
PostgreSQL advisory lock (`2042801`) used by the historical Alembic runner, and
supports two explicit states:

- an empty database is migrated through V1..latest;
- the frozen Alembic head is schema-validated, baselined at version 4, and then
  migrated through V5..latest.

A non-empty mismatch fails before Flyway history is created. Blind
`baselineOnMigrate` is intentionally not enabled, and `alembic_version` remains
in place throughout the Python rollback window.

Alembic-to-Flyway translation notes:

- Alembic downgrade functions are not ported because Flyway in this module is used as a forward-only migration runner.
- Integer primary keys are expressed as PostgreSQL identity columns. This preserves the generated-ID behavior without introducing schema redesign.
- Alembic `server_default` expressions are translated directly into PostgreSQL SQL defaults such as `CURRENT_TIMESTAMP`, `TRUE`, `FALSE`, and string literals.

Quick verification from the repo root:

```powershell
backend-java\mvnw.cmd verify
```

`verify` covers the unit test suite plus the Testcontainers-backed integration phase that exercises Flyway migrations when Docker is available.
Formatting and structural style checks run automatically during Maven's `validate` phase, so `compile`, `test`, and `verify` fail before compilation when Java style is invalid.

To run the canonical read-only style check or optionally apply the formatter from the repo root:

```powershell
backend-java\mvnw.cmd validate
backend-java\mvnw.cmd spotless:apply
```

Manual endpoint check on the default application port:

```powershell
backend-java\mvnw.cmd -pl application -am package
java -jar backend-java\application\target\good-news-application-0.0.1-SNAPSHOT-exec.jar
curl.exe http://127.0.0.1:8080/api/health
```

Java image publication, staging and production rollout, and rollback are
documented in [`docs/java-deployment.md`](../docs/java-deployment.md).
