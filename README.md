# Good News

Personal news aggregator that ingests RSS/Atom feeds, ranks posts with Gemini against your preference profile, and delivers scheduled email digests.

Runs in Google Cloud: https://good-news-am26.web.app

## Architecture

| Component | Where |
|-----------|-------|
| Frontend (React/Vite) | Firebase Hosting |
| Backend (FastAPI monolith) | Cloud Run `good-news-app` (us-central1, scale-to-zero) |
| Database | Neon Postgres (`GOOD_NEWS_DATABASE_URL`, sslmode=require) |
| Post analysis | Gemini API (`gemini-2.5-flash-lite` by default) |
| Periodic jobs | Cloud Scheduler → `POST /internal/jobs/source-sync`, `POST /internal/jobs/digests` (Google OIDC) |
| Email digests | Gmail SMTP — configured in the Settings tab, password stored encrypted in the DB |
| Auth | Firebase Auth (Google sign-in) + email allowlist on the backend |
| Secrets | GCP Secret Manager: `good-news-db-url`, `good-news-app-master-key`, `good-news-gemini-api-key` |

The frontend API layer routes each operation through a versioned ownership map.
Production currently assigns every operation to the Python Cloud Run origin
(`VITE_CONTENT_API_ORIGIN`); `VITE_JAVA_API_ORIGIN` is reserved for staged
strangler cutovers. Firebase Hosting rewrites `/api/**` remain a fallback.

## Frontend tabs

| Tab | Description |
|-----|-------------|
| **Feed** | Main post feed. Sort by **By match** (AI-ranked relevance) or **By date** (newest first). |
| **Want to Read** | Posts saved for later reading. |
| **Sources** | Manage and sync RSS/Atom sources. |
| **Digest** | Browse sent email digests. |
| **Preferences** | View the AI-derived preference profile (topics, verdicts). |
| **Settings** | Configure email delivery, digest schedule, SMTP. |
| **Monitoring** | Source health, system health, LLM queue, capacity. |

## Deployment

Push to `master` triggers the build-once/promote release pipeline:

1. The `Plan applicable checks` job maps changed paths to one parallel
   validation layer: Python, frontend, production-image, Java, and
   differential-contract checks. Pull requests skip unaffected checks; trusted
   `master` pushes run all five to produce a complete release candidate.
2. The `Quality gate` job is the single stable required status. Failed or
   cancelled checks fail the gate; path-filtered Java and contract jobs may be
   skipped.
3. After the gate, a trusted `master` run publishes the tested backend and
   migration images, the production frontend, and their release manifest.
4. A successful trusted CI run on `master` triggers
   `.github/workflows/deploy.yml`, which validates the manifest, promotes both
   images by digest, runs the Flyway Cloud Run job, deploys and health-checks a
   tagged Cloud Run revision before sending it production traffic, and deploys
   the exact archived frontend.

Deploy does not rebuild artifacts or rerun a reduced test suite. Release
manifests and frontend candidates are retained in GitHub Actions for 14 days.
The tested image archives have the same retention; published SHA tags and
digest-addressed images are governed by the Artifact Registry cleanup policy.
That policy must retain deployed digests and may remove untagged or undeployed
candidates after the 14-day manual-promotion window.

GitHub authenticates to GCP via Workload Identity Federation — no key files.
All changes land on `master` through pull requests. Both privileged Deploy jobs
use the GitHub `production` environment; configure that environment and the
Workload Identity Provider to allow only `master`, with optional required
reviewers for production promotion.

Run the `Deploy` workflow manually with its default `validate` operation to
verify Workload Identity Federation, the installed gcloud version, and
authenticated access to Artifact Registry, the `db-migrate` Cloud Run job, the
`good-news-app` Cloud Run service, and Firebase Hosting. The validation performs
read-only cloud queries; its only local mutation is configuring Docker
authentication on the ephemeral runner.

A manual production deployment requires selecting `deploy` and supplying both
the successful CI run ID and its full commit SHA while dispatching the workflow
from `master`. The workflow rejects runs that did not complete the full quality
gate, non-`master` or non-push runs, missing or expired artifacts, mismatched
manifests or digests, and candidates that are no longer the tip of `master`. It
never rebuilds a missing candidate.

To roll back the backend, shift Cloud Run traffic to a known-good retained
revision. Rollback intentionally uses the cloud provider's retained release
history rather than rerunning an old candidate deployment:

```shell
gcloud run services update-traffic good-news-app \
  --region us-central1 \
  --project PROJECT_ID \
  --to-revisions REVISION=100
```

Roll back the frontend to a known-good release from the Firebase Hosting release
history. Database migrations remain forward-only and are not reverted as part
of an application rollback.

The Alembic chain is frozen for Python rollback compatibility. Flyway owns all
new production schema changes; see
[the production migration runbook](docs/flyway-production-migration-runbook.md).
The Java reactor contains separate serving, migration, and contract executable
modules; see [the Java module README](backend-java/README.md).

Cloud Scheduler jobs (`source-sync` every 30 min, `daily-digest` hourly) call the
`/internal/jobs/*` endpoints with an OIDC token from `scheduler-invoker@…`;
the backend verifies issuer, audience, and service-account email.

## Local development

No Docker. Run the backend against a Neon dev branch:

```powershell
python -m pip install -e './backend[dev]'
# fill .env from .env.example, load it into the shell, then:
cd backend
uvicorn app.main:app --reload
```

Frontend:

```powershell
# Requires Node >=22.12.0.
npm ci --prefix frontend
npm run dev --prefix frontend   # proxies /api to localhost:8000
```

With `GOOD_NEWS_FIREBASE_PROJECT_ID` unset, auth middleware is disabled locally.

## Tests

```powershell
pytest backend/tests/unit backend/tests/api -q
backend-java\mvnw.cmd verify
npm run test --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

## Operations

- Runtime status: the in-app Monitoring page backed by `/api/monitoring/summary`
- Health: `GET https://good-news-app-446870476468.us-central1.run.app/api/health` (public)
- Budget alert on the billing account guards the free tier (expected spend: $0/month)
- Migration plan history: [docs/firebase-migration-plan.md](docs/firebase-migration-plan.md)
