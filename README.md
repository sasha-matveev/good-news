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

The frontend calls Cloud Run directly (`VITE_CONTENT_API_ORIGIN` baked at build time); Firebase Hosting rewrites `/api/**` exist as a fallback.

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

Push to `master` triggers `.github/workflows/deploy.yml`:

1. Backend + frontend tests
2. Docker image → Artifact Registry
3. Cloud Run Job `db-migrate` (Alembic `upgrade head` under an advisory lock)
4. `gcloud run deploy good-news-app` (secrets from Secret Manager)
5. Vite build → `firebase deploy --only hosting`

GitHub authenticates to GCP via Workload Identity Federation — no key files.
All changes land on `master` through pull requests.

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
npm ci --prefix frontend
npm run dev --prefix frontend   # proxies /api to localhost:8000
```

With `GOOD_NEWS_FIREBASE_PROJECT_ID` unset, auth middleware is disabled locally.

## Tests

```powershell
pytest backend/tests/unit backend/tests/api -q
npm run test --prefix frontend
```

## Operations

- Logs and metrics: Cloud Logging / Cloud Monitoring for `good-news-app`
- Health: `GET https://good-news-app-446870476468.us-central1.run.app/api/health` (public)
- Budget alert on the billing account guards the free tier (expected spend: $0/month)
- Migration plan history: [docs/firebase-migration-plan.md](docs/firebase-migration-plan.md)
