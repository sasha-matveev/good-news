# Good News

Personal news aggregator that ingests RSS/Atom feeds, ranks posts with a local LLM against your preference profile, and delivers scheduled email digests.

## Frontend

The frontend (port 5173) provides seven tabs:

| Tab | Description |
|-----|-------------|
| **Feed** | Main post feed. Sort by **By match** (AI-ranked relevance) or **By date** (newest first). |
| **Want to Read** | Posts saved for later reading. |
| **Sources** | Manage and sync RSS/Atom sources. |
| **Digest** | Browse sent email digests. |
| **Preferences** | View the AI-derived preference profile (topics, verdicts). |
| **Settings** | Configure email delivery, digest schedule, SMTP. |
| **Monitoring** | In-app operator dashboard: source health, system health, LLM queue, capacity, and a direct link to Grafana. |

## Services

| Service | Role |
|---------|------|
| `postgres` | Primary database |
| `db-migrate` | One-shot Alembic migration runner |
| `analysis-llm-service` | AI-backed post ranking and analysis via Ollama |
| `source-ingestion-service` | Feed fetch, parse, and normalize |
| `delivery-service` | Email digest scheduling and dispatch |
| `content-api-service` | REST API consumed by the frontend |
| `frontend` | Nginx-served Vite build |
| `ollama` | Local LLM runtime |

Optional services (off by default):

- `smtp` — Mailhog for email testing
- `prometheus`, `grafana`, `loki`, `otel-collector`, `grafana-image-renderer` — observability stack

## Operator flows

Two supported flows:

1. **`build + tests + deploy`** — required after any code change; rebuilds images, runs tests, runs migrations, starts services.
2. **`restart`** — runtime recovery or config re-read only; does not rebuild images or run tests.

Canonical entrypoints:

```powershell
.\scripts\deploy.ps1
.\scripts\restart-runtime-service.ps1 -Services all
.\scripts\restart-runtime-service.ps1 -Services content-api-service
```

For the full operator reference (start, health, logs, stop, recovery) see [docs/local-operator-playbook.md](docs/local-operator-playbook.md).

## Default local runtime

`deploy.ps1` boots the full usable system in one command:

1. Starts `postgres` and waits for readiness
2. Runs the explicit `db-migrate` step
3. Starts `ollama`, pulls the configured model if missing
4. Builds and starts all app services

```powershell
.\scripts\deploy.ps1
```

If secrets live outside the repo, pass the file explicitly:

```powershell
.\scripts\deploy.ps1 -SecretsFilePath "C:\path\to\dev-secrets.env"
```

Raw Compose equivalent:

```powershell
. .\scripts\load-dev-secrets.ps1
docker compose --profile ai up -d postgres ollama
docker compose --profile migration run --rm --no-deps db-migrate
$env:GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN = "http://127.0.0.1:8000"
$env:GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN = "http://127.0.0.1:5173"
.\scripts\pull-ollama-model.ps1
docker compose --profile ui --profile ai up -d analysis-llm-service source-ingestion-service delivery-service content-api-service frontend
```

Backend services fail fast on startup if the database schema is missing or behind Alembic head.

## Local setup

Run from the repo root.

1. Install dependencies:

```powershell
.\scripts\bootstrap.ps1
```

2. Provide runtime secrets.

Required secrets:

- `GOOD_NEWS_APP_MASTER_KEY`
- `GOOD_NEWS_POSTGRES_PASSWORD`

Supported sources (tried in this order):

1. Pre-set shell environment variables
2. External `.env`-style file at `$HOME/.good-news/dev-secrets.env` (or the path in `GOOD_NEWS_LOCAL_SECRETS_FILE`)
3. Windows Credential Manager (optional convenience fallback)
4. Recovery from an existing running container environment

Example secrets file:

```dotenv
GOOD_NEWS_APP_MASTER_KEY=<master-key>
GOOD_NEWS_POSTGRES_PASSWORD=<postgres-password>
```

To write secrets from Credential Manager into the local `.env` file once (so subprocesses and agents can read them):

```powershell
.\scripts\export-secrets-to-dotenv.ps1
```

To create or refresh Credential Manager entries:

```powershell
.\scripts\bootstrap.ps1 -AppMasterKey "<master-key>" -PostgresPassword "<postgres-password>"
```

3. Load secrets into the current shell:

```powershell
. .\scripts\load-dev-secrets.ps1
```

4. Verify secret presence:

```powershell
.\scripts\bootstrap.ps1 -CheckSecrets
```

## Minimum acceptance checks

```powershell
curl.exe -i http://127.0.0.1:8000/api/health
curl.exe -i http://127.0.0.1:8000/api/posts
curl.exe -i http://127.0.0.1:5173/api/posts
```

- `postgres` is `healthy`
- `content-api-service` is `healthy`
- `frontend` is `running`

## Ollama model

The local AI runtime uses `llama3.2:3b-instruct-q4_K_M`. `deploy.ps1` pulls it automatically. To pre-warm explicitly:

```powershell
docker compose --profile ai up -d ollama
.\scripts\pull-ollama-model.ps1
```

Configured via:

- `GOOD_NEWS_OLLAMA_HOST`
- `GOOD_NEWS_OLLAMA_PORT`
- `GOOD_NEWS_OLLAMA_MODEL`

## Observability

The observability stack runs as an opt-in profile and does not affect the default runtime footprint.

```powershell
docker compose --profile observability up -d grafana prometheus loki otel-collector grafana-image-renderer
```

Smoke test:

```powershell
.\scripts\validation\verify-observability-stack.ps1
```
