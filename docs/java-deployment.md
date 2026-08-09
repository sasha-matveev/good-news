# Java deployment

The Java serving application is part of `.github/workflows/ci.yml`. Its job
runs the Maven test suite and builds the serving and migration images. On a
`master` push, the workflow's `Deploy` job publishes those tested images, runs
the migration image, deploys `good-news-java`, and verifies `/api/health`.
There is no intermediate staging service or separate Java deployment workflow.

Browser operation routing remains an independent deployment decision in
`frontend/src/lib/api.ts`; changing backend ownership does not require a
different Java deployment mechanism.

Java application startup does not run Flyway. Schema changes continue to run
only through the dedicated `db-migrate` Cloud Run job and migration image.

## Configuration

The Java jobs use the existing repository variables `GCP_PROJECT_ID`,
`GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, and
`ALLOWED_EMAILS` from the production environment.

The current production resource names are the defaults, so the existing
deployment configuration works without Java-specific variables:

- runtime service account: `good-news-app@<project>.iam.gserviceaccount.com`;
- database secret: `good-news-db-url`;
- application master-key secret: `good-news-app-master-key`;
- Gemini secret: `good-news-gemini-api-key`;
- Firebase project: the configured Google Cloud project;
- scheduler identity: `scheduler-invoker@<project>.iam.gserviceaccount.com`;
- public API origin: the current Python production origin;
- public frontend origin: `https://<project>.web.app`.

The following optional repository or production-environment variables override
those defaults without changing the workflow:

| Variable | Purpose |
| --- | --- |
| `JAVA_RUNTIME_SERVICE_ACCOUNT` | Java Cloud Run runtime identity |
| `JAVA_DATABASE_URL_SECRET` | Secret Manager name containing `GOOD_NEWS_DATABASE_URL` |
| `JAVA_APP_MASTER_KEY_SECRET` | Secret Manager name containing the application master key |
| `JAVA_GEMINI_API_KEY_SECRET` | Secret Manager name containing the Gemini API key |
| `JAVA_FIREBASE_PROJECT_ID` | Firebase project accepted by Java authentication |
| `JAVA_SCHEDULER_INVOKER` | Identity allowed to call `/internal/jobs/*` |
| `JAVA_OIDC_AUDIENCE` | Audience required for scheduler requests |
| `JAVA_PUBLIC_CONTENT_API_ORIGIN` | Public API origin used in generated links |
| `JAVA_PUBLIC_FRONTEND_ORIGIN` | Public frontend origin used in generated links and CORS |

Before transferring an operation or scheduler to Java, set its public origin or
OIDC audience override to the stable `good-news-java` service URL as needed.

## Resource contract

The Java service uses this resource policy:

- 1 CPU, 512 MiB memory, concurrency 20, and request timeout 300 seconds;
- min instances 0 and max instances 1;
- R2DBC initial pool size 0 and max pool size 4;
- `/api/health` startup probe every 5 seconds with 12 failures allowed.

Cloud Run creates the new `good-news-java` revision and sends service traffic to
it. The workflow then checks `/api/health`. The endpoint checks database
connectivity and required schema and does not mutate the schema.

## Release and rollback

The deploy job runs only for a successful `master` CI run and consumes the Java
images built by that same run. Java, Python, migration, and frontend deployment
are one job, so a failure makes the single workflow visibly fail.

Rollback uses the normal Cloud Run revision mechanism: direct the affected Java
service back to its previous healthy revision. Frontend operation ownership and
Cloud Scheduler targets are changed separately, so they can be rolled back
without changing the image deployment pipeline or database schema.
