# Good News reactive Java backend

The module targets Java 21 and Spring Boot 3.5.16. It is the shadow backend for
the production strangler migration; browser production traffic remains owned by
Python until a later ownership PR changes the frontend operation map.

## Production readiness contract

- `GET /api/health` is public and returns `{"status":"ok"}` only when the
  database has the required schema. Database or schema failure
  returns `503` with `{"status":"error","reason":"database or required schema is not ready"}`.
- `GET /actuator/health` is public. Other `/actuator/**` routes require
  authentication. Prometheus is neither exposed nor included as a runtime
  dependency; Cloud Logging structured request events and Micrometer's in-process
  registry are the current Cloud Monitoring integration seam.
- Every response carries `X-Good-News-Backend: java` and `X-Correlation-ID`.
  Request logs and HTTP counters/timers include backend, method, route, and
  status dimensions.
- CORS permits the configured `GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN` plus the local
  Vite origins. Authorization, content type, and correlation headers are
  accepted in browser preflight requests.

## Database connection budget and timeouts

The Java service uses an explicit R2DBC pool. Defaults are deliberately small
for the first shadow deployment:

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

Flyway SQL migrations live in `src/main/resources/db/migration` and are driven from the existing `good-news.database.*` properties at application startup.

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
backend-java\mvnw.cmd spring-boot:run
curl.exe http://127.0.0.1:8080/api/health
curl.exe http://127.0.0.1:8080/actuator/health
curl.exe -i http://127.0.0.1:8080/actuator/prometheus
```

The final command must not return an unauthenticated metrics payload.
