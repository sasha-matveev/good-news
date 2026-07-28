# Flyway production migration runbook

Flyway is the only production schema writer after issue #54. Python continues
to serve API and scheduler traffic during this phase, and `alembic_version`
must remain untouched so a Java application rollout can be abandoned without a
schema rollback.

## Preconditions

- Use the exact Java migration image built from the deployment commit.
- Confirm the database reports Alembic revision
  `20260725_01_digest_slots`.
- Stop if an unexpected table, column, constraint, or index is present. The
  migration command intentionally refuses to baseline a mismatched database.
- Do not use Flyway `baselineOnMigrate`.
- Confirm the Python API and both scheduler paths are healthy before starting.

## Backup and restore rehearsal

Run this procedure first against a production-like Neon branch or restored
copy, never first against production:

1. Create a provider snapshot/branch and record its immutable identifier.
2. Export a portable backup with `pg_dump --format=custom --no-owner`.
3. Restore it into an empty rehearsal database with
   `pg_restore --clean --if-exists --no-owner`.
4. Run the migration image:

   ```shell
   docker run --rm \
     --env GOOD_NEWS_DATABASE_URL \
     MIGRATION_IMAGE
   ```

5. Run the same command a second time. It must succeed without adding another
   history row or changing application rows.
6. Verify representative source, post, read-later, digest, settings, and
   feedback values and row counts against the source copy.
7. Start the Python image against the migrated copy and smoke-test
   `/api/health`, a read-only feed request, and authenticated test invocations
   of the source-sync and digest scheduler routes.
8. Restore the pre-migration backup into another empty database and repeat the
   row-count and representative-value checks. Record the commands, snapshot
   identifier, image digest, timestamps, and results in the release evidence.

## Production execution

CI builds and tests the Python serving image and dedicated Java migration image
once. After the complete `Quality gate` succeeds for a trusted `master` push,
the deployment workflow reads the release manifest and promotes those exact
digest-addressed images. It does not rebuild either image. The `db-migrate`
Cloud Run job runs the verified `MigrationApplication` image. The serving
`GoodNewsApplication` artifact does not contain migration code or Flyway SQL.
The runner:

1. acquires PostgreSQL advisory lock `2042801`;
2. validates the frozen Alembic revision and schema;
3. creates Flyway baseline version 4;
4. records/applies V5 and later migrations;
5. releases the lock.

After the job succeeds, Deploy installs the verified Python image digest
without production traffic, health-checks the tagged URL of the newly created
Cloud Run revision, and only then moves production traffic to it. Then perform
the same API and scheduler smoke checks used in rehearsal. Record the source CI
run, commit, both image digests, frontend artifact digest, and Cloud Run
revision from the workflow summary. Preserve the provider snapshot and backup
through the rollback window.

Application rollback is a Cloud Run revision change. Migrations are
forward-only and are not rolled back with application code. Frontend rollback
uses a known-good Firebase Hosting release. Do not attempt rollback by manually
promoting an older candidate: the freshness guard rejects any candidate that is
not the current `master` tip, preventing an older queued deployment from
overwriting a newer release.

GitHub Actions release manifests, frontend archives, and tested image archives
are retained for 14 days. Artifact Registry must have a cleanup policy that
preserves deployed digests while removing untagged or undeployed candidates
after the same manual-promotion window. A missing or expired candidate is a
hard failure and must never be rebuilt during Deploy.
