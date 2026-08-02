# Java production shadow deployment

The Java serving application is released as the same immutable image candidate
that passes Maven verification, the differential contract suite, a high-severity
dependency review, container startup, and `/api/health` in CI. The candidate is
published to Artifact Registry by digest. The existing Python release remains
the production owner and its deploy workflow is unchanged.

Java startup does not run Flyway. Schema changes continue to run only through
the dedicated `db-migrate` Cloud Run job and the separate migration image.

## GitHub environment configuration

Configure both the `staging` and `production` GitHub environments with the
following variables. Staging values must identify staging resources; never
reuse the production database secret in the staging environment.

| Variable | Purpose |
| --- | --- |
| `GCP_PROJECT_ID` | Google Cloud project containing the environment |
| `GCP_REGION` | Artifact Registry and Cloud Run region |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | GitHub Workload Identity provider |
| `GCP_SERVICE_ACCOUNT` | CI deploy identity |
| `JAVA_RUNTIME_SERVICE_ACCOUNT` | Runtime identity for the Java service |
| `JAVA_DATABASE_URL_SECRET` | Secret Manager name containing `GOOD_NEWS_DATABASE_URL` |
| `JAVA_APP_MASTER_KEY_SECRET` | Secret Manager name containing the shared application master key |
| `JAVA_GEMINI_API_KEY_SECRET` | Secret Manager name containing the Gemini API key |
| `JAVA_FIREBASE_PROJECT_ID` | Firebase project accepted by Java authentication |
| `ALLOWED_EMAILS` | Comma-separated backend allowlist |
| `JAVA_SCHEDULER_INVOKER` | Identity allowed to call `/internal/jobs/*` |
| `JAVA_OIDC_AUDIENCE` | Required audience for controlled direct scheduler requests |
| `JAVA_PUBLIC_CONTENT_API_ORIGIN` | Public API origin used in generated links |
| `JAVA_PUBLIC_FRONTEND_ORIGIN` | Public frontend origin used in generated links and CORS |

The deploy identity needs Artifact Registry read, Cloud Run deploy, service
account user, and Secret Manager metadata permissions. The runtime identity
needs access to the three configured secret versions and the external services
used in the selected environment.

## Resource contract

The workflow deploys `good-news-java-staging` with staging traffic, then pauses
at the protected `production` environment before deploying `good-news-java`.
The production revision receives a tagged diagnostic URL but no untagged
traffic. The frontend operation-ownership map is checked to ensure every
production operation still points to Python.

Both services use these explicit limits:

- 1 CPU, 512 MiB memory, concurrency 20, and request timeout 300 seconds;
- min instances 0 and max instances 1;
- R2DBC initial pool size 0 and max pool size 4, giving a four-connection
  maximum for the shadow service;
- `/api/health` startup probe every 5 seconds with 12 failures allowed.

The health endpoint checks both database connectivity and required schema. An
unavailable database or incompatible schema therefore keeps the revision out of
service, and the probe retries automatically after the database recovers. It
does not mutate the schema.

## Release procedure

1. Merge a candidate whose `CI` workflow is green. Record its CI run ID and
   40-character commit SHA.
2. Run `Deploy Java Shadow` with operation `validate` and correct any missing
   environment variables, IAM grants, secrets, or registry access.
3. Run it again with operation `deploy`, the recorded run ID, and SHA. The
   workflow rejects candidates that are not the current green `master` commit.
4. Use the staging revision URL from the workflow summary to build or run the
   existing staging frontend with:

   ```text
   VITE_DEPLOY_ENV=staging
   VITE_JAVA_API_ORIGIN=<staging revision URL>
   VITE_API_BACKEND_OVERRIDE=java
   ```

5. Before approving the protected production job, sign in through staging and
   exercise Feed, reactions, Sources, Preferences, Settings, Digests, and
   Monitoring. Verify both Monitoring summary and queue. Invoke internal jobs
   only with the staging scheduler identity and confirm their staging-only
   persisted and external effects. The local differential suite must already be
   green in the source CI run.
6. Approve the production environment. The same image digest is deployed to
   `good-news-java` with zero normal traffic. Use only the tagged URL printed in
   the summary for controlled `/api/health` and authenticated read smoke tests.
   Do not target it from Cloud Scheduler or change `API_OPERATION_OWNERS`.

For a database/schema failure rehearsal, temporarily point the staging service
at an unavailable or pre-migration staging database. Confirm the startup probe
remains unhealthy, restore the correct secret/schema, and confirm the same
revision becomes healthy without running Flyway during application startup.

## Rollback

Delete or redeploy the Java shadow revision if its direct smoke fails. No
production traffic or scheduler target points at it, so the Python service,
Firebase Hosting deployment, migration job, and existing rollback procedure do
not change.
