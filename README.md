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

The repository has one workflow: `.github/workflows/ci.yml`.

1. On pull requests, `Detect changes` selects the affected Python, Java,
   frontend, and backend-contract jobs. Unaffected jobs are skipped.
2. On every push to `master`, all tests and all three application builds run.
3. After `Quality gate` succeeds on `master`, the `Deploy` job publishes the
   tested images, runs Flyway, deploys the Python and Java Cloud Run services,
   health-checks them, and deploys the tested frontend to Firebase Hosting.

The deploy job never runs for a pull request or another branch. It consumes the
artifacts built earlier in the same workflow run instead of rebuilding them.
Container images are tagged with the source commit SHA.

GitHub authenticates to GCP via Workload Identity Federation — no key files.
All changes land on `master` through pull requests. The privileged `Deploy` job
uses the GitHub `production` environment; configure that environment and the
Workload Identity Provider to allow only `master`, with optional required
reviewers for production promotion.

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
