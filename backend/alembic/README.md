# Frozen Alembic history

Production migration ownership moved to Flyway in issue #54. The Alembic chain
is frozen at revision `20260725_01_digest_slots`; do not add production schema
changes here.

The files and the `alembic_version` table remain in place for the Python
application rollback window. New coexistence-safe schema changes must be added
as forward-only Flyway migrations under
`backend-java/src/main/resources/db/migration/`.

Alembic and Flyway must never be invoked concurrently. Both historical runners
use PostgreSQL advisory lock `2042801`, but `.github/workflows/deploy.yml`
deliberately has only one schema-writing step: the Java Flyway Cloud Run job.
