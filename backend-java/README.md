# backend-java observability

## Database migrations

Flyway SQL migrations live in `src/main/resources/db/migration` and are driven from the existing `good-news.database.*` properties at application startup.

Alembic-to-Flyway translation notes:

- Alembic downgrade functions are not ported because Flyway in this module is used as a forward-only migration runner.
- Integer primary keys are expressed as PostgreSQL identity columns. This preserves the generated-ID behavior without introducing schema redesign.
- Alembic `server_default` expressions are translated directly into PostgreSQL SQL defaults such as `CURRENT_TIMESTAMP`, `TRUE`, `FALSE`, and string literals.

The backend exposes these unauthenticated Actuator endpoints on the main application port:

- `/actuator/health`
- `/actuator/prometheus`

Quick verification from the repo root:

```powershell
mvn -f backend-java\pom.xml verify
```

`verify` covers the unit test suite plus the Testcontainers-backed integration phase that exercises Flyway migrations when Docker is available.

Manual endpoint check on the default application port:

```powershell
mvn -f backend-java\pom.xml spring-boot:run
curl.exe http://127.0.0.1:8080/actuator/health
curl.exe http://127.0.0.1:8080/actuator/prometheus
```
