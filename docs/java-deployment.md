# Java deployment

The Java serving application is part of the repository's regular release
pipeline. CI builds and smoke-tests the serving image once, publishes that
tested image to Artifact Registry by digest, and records it in the same release
manifest as the Python backend, migration image, and frontend artifact.

The `Deploy` workflow deploys the immutable Java image to
`good-news-java-staging`, verifies its public health endpoint, and promotes the
healthy staging revision. It then deploys the exact same digest to
`good-news-java`, verifies the production revision, and promotes it within that
service. Browser operation routing remains an independent deployment decision
in `frontend/src/lib/api.ts`; changing backend ownership does not require a
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

The staging job accepts the same names with a `JAVA_STAGING_` prefix, for
example `JAVA_STAGING_DATABASE_URL_SECRET`. A staging-specific value takes
precedence over its shared `JAVA_` counterpart. This lets the service move to
isolated staging secrets and identities without changing the deployment code.

Before transferring an operation or scheduler to Java, set its public origin or
OIDC audience override to the stable `good-news-java` service URL as needed.

## Resource contract

Both Java services use the same permanent resource policy:

- 1 CPU, 512 MiB memory, concurrency 20, and request timeout 300 seconds;
- min instances 0 and max instances 1;
- R2DBC initial pool size 0 and max pool size 4;
- `/api/health` startup probe every 5 seconds with 12 failures allowed.

Each deployment first creates a tagged revision with no traffic, checks
`/api/health`, and only then assigns that service's traffic to the exact healthy
revision. The health endpoint checks database connectivity and required schema,
so an unavailable or incompatible database cannot be promoted. It does not
mutate the schema.

## Release and rollback

The Java staging and production jobs consume only a current successful `master`
CI candidate whose Quality gate passed. A failed Java job does not prevent the
independent Python deployment job from completing, but it makes the overall
`Deploy` workflow visibly fail.

Rollback uses the normal Cloud Run revision mechanism: direct the affected Java
service back to its previous healthy revision. Frontend operation ownership and
Cloud Scheduler targets are changed separately, so they can be rolled back
without changing the image deployment pipeline or database schema.
