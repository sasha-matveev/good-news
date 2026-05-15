# Good News MVP

Task 4 adds scheduled ingestion, persisted posts, the Feed page, and a runtime requirement that the local stack apply Alembic head before the content API service is considered healthy.
Task 5 adds the local Ollama model runtime, AI-backed post analysis, inspectable ranking, and the Preference Profile page.
Phase 3 extracts `analysis-llm-service` as the first externalized runtime, so model-facing enrichment now crosses an explicit service boundary instead of running in-process inside the content API runtime.
Phase 4 extracts `source-ingestion-service`, so source onboarding and sync/fetch/parse/normalize now cross a separate ingestion runtime boundary before handing posts into analysis.

## Frontend features

The frontend (port 5173) provides seven tabs:

| Tab | Description |
|-----|-------------|
| **Feed** | Main post feed. Sort by **By match** (AI-ranked relevance) or **By date** (newest first) using the sort toggle. |
| **Want to Read** | Posts saved for later reading, sorted independently from the feed. |
| **Sources** | Manage and sync RSS/Atom sources. |
| **Digest** | Browse sent email digests. |
| **Preferences** | View the AI-derived preference profile (topics, verdicts). |
| **Settings** | Configure email delivery, digest schedule, SMTP. |
| **Monitoring** | In-app operator dashboard: source health, system health, LLM queue, capacity, and a direct link to Grafana. |

The Monitoring tab is the primary in-app operator entry point. For Docker-level monitoring use [docs/local-operator-playbook.md](docs/local-operator-playbook.md).

## Supported local operator flows

The current supported operator target is one local instance built from local Docker images.

There are only two supported operator flows:

1. `build + tests + deploy`
2. `restart` one service or all services

`build + tests + deploy` is the required operator flow after repo code changes. Blocking tests must pass before deploy. Migrations are required when the target revision needs them. Downtime is acceptable, but local data must be preserved.

`restart` is only for runtime recovery or config re-read when you are not trying to pick up new code. It does not rebuild images, run tests, or check whether the current image matches the repo state. Stale runtime after code changes is unsupported behavior.

The intended script contract is:

- root `scripts/` keeps ops and SDLC entrypoints only;
- verification, replay, disposable, and acceptance helpers belong under `scripts/validation/`.

Canonical operator entrypoints:

- `.\scripts\deploy.ps1`
- `.\scripts\restart-runtime-service.ps1 -Services all`
- `.\scripts\restart-runtime-service.ps1 -Services content-api-service`

For the short operator-facing start, restart, health, logs, stop, and recovery flow for the supported local instance, use [docs/local-operator-playbook.md](/C:/Users/ytype/dev/projects/good-news/docs/local-operator-playbook.md). For the accepted operator contract, use [docs/superpowers/specs/2026-05-12-local-operator-contract.md](/C:/Users/ytype/dev/projects/good-news/docs/superpowers/specs/2026-05-12-local-operator-contract.md).

## Default usable local runtime

The supported local boot path now defaults to one usable system, not an API-only subset.

Default service set:

- `postgres`
- `db-migrate`
- `ollama`
- `analysis-llm-service`
- `source-ingestion-service`
- `delivery-service`
- `content-api-service`
- `frontend`

Optional services stay optional:

- `smtp` stays off unless you are explicitly running email verification;
- observability services stay off unless you are explicitly validating operator visibility.

The Compose file also applies CPU, memory, and log-file bounds to each service so Docker cannot grow unchecked during normal local use.

`deploy.ps1` is now the canonical one-command local boot helper. On the no-argument path it:

1. starts `postgres`;
2. waits for Postgres readiness;
3. runs the explicit `db-migrate` step;
4. starts `ollama` under the `ai` profile;
5. pulls the configured Ollama model when it is missing;
6. starts the default usable app services;
7. enables the `ui` and `ai` profiles automatically for the supported product runtime;
8. fills loopback public origins for local use when they were not pre-set;
9. rebuilds the app images before starting runtime services so the local stack matches the current repo code.

Recommended local deploy:

```powershell
.\scripts\deploy.ps1
```

If the current operator or agent context must use a specific external secrets file, pass it explicitly:

```powershell
.\scripts\deploy.ps1 -SecretsFilePath "C:\path\outside\the\repo\dev-secrets.env"
```

Raw Compose equivalent for the default usable local system:

```powershell
. .\scripts\load-dev-secrets.ps1
docker compose --profile ai up -d postgres ollama
docker compose --profile migration run --rm --no-deps db-migrate
$env:GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN = "http://127.0.0.1:8000"
$env:GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN = "http://127.0.0.1:5173"
.\scripts\pull-ollama-model.ps1
docker compose --profile ui --profile ai up -d analysis-llm-service source-ingestion-service delivery-service content-api-service frontend
```

The same shell-loading helper also accepts an explicit override when `$HOME` differs between operator and agent contexts:

```powershell
. .\scripts\load-dev-secrets.ps1 -SecretsFilePath "C:\path\outside\the\repo\dev-secrets.env"
```

The helper script above runs that same sequence for the default usable runtime and waits for Postgres before the explicit migration step. `db-migrate` is a one-shot service behind the `migration` profile, so routine `docker compose up -d` does not silently reintroduce self-migration behavior.

If you intentionally want to reuse already-built images, that is no longer the supported flow after code changes. Use `restart` only when you are not trying to pick up new code.

Supported startup contract:

1. start `postgres`;
2. wait for Postgres readiness;
3. run the explicit `db-migrate` step;
4. start the required app services for the usable system.

Do not treat `docker compose up -d --build` by itself as a supported boot flow anymore. Backend services now fail fast when the schema is missing or behind Alembic head.

If you prefer the raw Compose sequence for API-only work:

```powershell
. .\scripts\load-dev-secrets.ps1
docker compose up -d postgres
docker compose --profile migration run --rm --no-deps db-migrate
docker compose up -d content-api-service
```

The frontend container serves a production Vite build rather than a live Vite dev runtime.

Shut optional services back down when you are done with them:

```powershell
docker compose stop smtp
```

For the short operator-facing start, health, logs, stop, and recovery flow for the supported local instance, use [docs/local-operator-playbook.md](/C:/Users/ytype/dev/projects/good-news/docs/local-operator-playbook.md).

## Local setup

Run from `C:\Users\ytype\dev\projects\good-news`.

1. Install Python and frontend dependencies:

```powershell
.\scripts\bootstrap.ps1
```

2. Use the supported platform-neutral local env/secrets contract.

Required runtime secrets:

- `GOOD_NEWS_APP_MASTER_KEY`
- `GOOD_NEWS_POSTGRES_PASSWORD`

Supported local paths:

- export both variables directly in your shell before running migrations or Compose;
- store them in an external `.env`-style file at `$HOME/.good-news/dev-secrets.env`;
- override that file location with `GOOD_NEWS_LOCAL_SECRETS_FILE`;
- optionally use Windows Credential Manager as an optional convenience fallback.

Example external secrets file:

```dotenv
GOOD_NEWS_APP_MASTER_KEY=<master-key>
GOOD_NEWS_POSTGRES_PASSWORD=<postgres-password>
```

For AI agents and automated subprocesses (which start fresh shell sessions without inherited env), write secrets from Credential Manager into the `.env` file once:

```powershell
.\scripts\export-secrets-to-dotenv.ps1
```

This writes `GOOD_NEWS_APP_MASTER_KEY`, `GOOD_NEWS_POSTGRES_PASSWORD`, and `POSTGRES_PASSWORD` into the local `.env` file (git-ignored) so every subprocess tool invocation can read them via Docker Compose's automatic `.env` loading.

If you want the optional Windows Credential Manager convenience path, create or refresh these entries:

```powershell
.\scripts\bootstrap.ps1 -AppMasterKey "<master-key>" -PostgresPassword "<postgres-password>"
```

Required secret names:

- `good-news/dev/app-master-key`
- `good-news/dev/postgres-password`

3. Load process-scoped environment variables into the current shell:

```powershell
. .\scripts\load-dev-secrets.ps1
```

If the current execution context should ignore its default home-derived file path, pass the external file explicitly:

```powershell
. .\scripts\load-dev-secrets.ps1 -SecretsFilePath "C:\path\outside\the\repo\dev-secrets.env"
```

`load-dev-secrets.ps1` uses this order:

1. pre-set shell environment values always win for each secret;
2. external `.env`-style file from `GOOD_NEWS_LOCAL_SECRETS_FILE` or `$HOME/.good-news/dev-secrets.env` fills only missing secrets;
3. Windows Credential Manager fallback fills only any still-missing secrets for the current Windows user;
4. if secrets are still missing and the selected local runtime project already exists, the script tries to recover the same two values from that project's existing container environment. `good-news` is the default project, and `-ComposeProjectName` keeps recovery aligned for other supported local project names.

When secret loading fails, the script reports the current Windows identity, `HOME`, `USERPROFILE`, the `GOOD_NEWS_LOCAL_SECRETS_FILE` override, the resolved secrets-file path, the selected Compose project, Docker fallback availability, and the Credential Manager targets it checked. Windows Credential Manager is per-user, so operator and agent contexts can legitimately see different stores.

It exports only the current shell session variables required by local runtime boot:

- `GOOD_NEWS_APP_MASTER_KEY`
- `GOOD_NEWS_POSTGRES_PASSWORD`
- `POSTGRES_PASSWORD`

User-facing origins can also be overridden explicitly when the app is exposed behind non-default hostnames or ports:

- `GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN`
- `GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN`

4. Verify secret presence without printing secret values:

```powershell
.\scripts\bootstrap.ps1 -CheckSecrets
```

The check prints the current execution identity, the home-path variables that control default file resolution, whether the external local secrets file exists, whether the optional Credential Manager entries exist, and whether the three process-scoped environment variables are currently loaded.

## Task 2 verification

```powershell
.\scripts\bootstrap.ps1
. .\scripts\load-dev-secrets.ps1
.\scripts\bootstrap.ps1 -CheckSecrets
python -m pytest backend/tests/unit/test_config.py backend/tests/unit/test_secret_store.py backend/tests/unit/test_db_session.py backend/tests/unit/test_secret_scripts.py -q
docker compose up -d postgres
python -m app.core.migration_runner
docker compose up -d content-api-service
```

These checks confirm the Task 2 foundations, but they are not the current acceptance contract by themselves. Use the whole-application verification flow below before closing an active slice.

## Whole-application verification

Load dev secrets into the current shell before any Compose or direct API verification:

```powershell
. .\scripts\load-dev-secrets.ps1
```

If the current shell is not the same Windows user context that owns the secrets, use the explicit override path instead:

```powershell
. .\scripts\load-dev-secrets.ps1 -SecretsFilePath "C:\path\outside\the\repo\dev-secrets.env"
```

Run the full local application with the profiles needed by the slice under verification:

- UI-required slices: add `--profile ui`
- SMTP/email verification slices: add `--profile verification`
- AI-required slices: add `--profile ai`
- Full-app acceptance across current slices: use both profiles

Use the supported deploy entrypoint:

```powershell
.\scripts\deploy.ps1
docker compose --profile ui --profile ai ps
```

Raw Compose equivalent:

```powershell
docker compose up -d postgres
docker compose --profile migration run --rm --no-deps db-migrate
docker compose --profile ui --profile ai up -d --build analysis-llm-service source-ingestion-service delivery-service content-api-service frontend
docker compose --profile ui --profile ai ps
```

Minimum acceptance checks:

- `postgres` is `healthy`
- `content-api-service` is `healthy`
- `frontend` is `running`
- `GET /api/health` succeeds on the `content-api-service` port
- `GET /api/posts` succeeds directly on the `content-api-service` port
- `GET /api/posts` succeeds through the frontend proxy on port `5173`

Example:

```powershell
curl.exe -i http://127.0.0.1:8000/api/health
curl.exe -i http://127.0.0.1:8000/api/posts
curl.exe -i http://127.0.0.1:5173/api/posts
```

Keep Docker limits in `docker-compose.yml` as the primary resource-control layer while doing this verification.

## Validation helpers

Validation helpers remain useful, but they are not the primary operator story. The accepted direction is for verification, replay, disposable, and acceptance helpers to live under `scripts/validation/` instead of on the root script surface.

## Task 4 runtime verification

Load dev secrets into the current shell before any Compose or direct API verification:

```powershell
. .\scripts\load-dev-secrets.ps1
```

If you are verifying directly from the host shell instead of the Compose migration service, apply schema changes explicitly first:

```powershell
python -m app.core.migration_runner
```

`python -m app.core.migration_runner` is the local host-shell equivalent of the Compose `db-migrate` step. For containerized startup and deploy-like verification, prefer the supported sequence `postgres -> db-migrate -> app services`.

Services no longer run migrations during startup. Each backend service now exits during boot if the database schema is missing or behind Alembic head.

For disposable Task 4 verification lanes specifically, the `ai` profile can still be omitted when the lane explicitly seeds the analysis stub instead of validating the supported local product runtime.

## Task 5 model bootstrap

Task 5 uses the Ollama model `llama3.2:3b-instruct-q4_K_M`.

The supported local product runtime now boots `ollama` by default and pulls this configured model automatically when it is missing. Phase 3 routes AI enrichment through `analysis-llm-service`, so the extracted runtime reaches a live Ollama container on the standard supported path.

If you want to prewarm the model explicitly before a deploy or before targeted AI-only verification, use:

```powershell
. .\scripts\load-dev-secrets.ps1
docker compose --profile ai up -d ollama
.\scripts\pull-ollama-model.ps1
.\scripts\deploy.ps1 -SkipTests
```

The model bootstrap helper also accepts the same explicit secrets-file override:

```powershell
.\scripts\pull-ollama-model.ps1 -SecretsFilePath "C:\path\outside\the\repo\dev-secrets.env"
```

The extracted analysis runtime reaches Ollama through:

- `GOOD_NEWS_OLLAMA_HOST`
- `GOOD_NEWS_OLLAMA_PORT`
- `GOOD_NEWS_OLLAMA_MODEL`

## Observability foundation

The local observability foundation runs as an opt-in Compose profile so it does not change the default app runtime footprint.

Foundation services:

- `grafana`
- `prometheus`
- `loki`
- `otel-collector`
- `grafana-image-renderer`

Boot the local stack directly:

```powershell
docker compose --profile observability up -d grafana prometheus loki otel-collector grafana-image-renderer
```

Run the disposable smoke verifier:

```powershell
.\scripts\validation\verify-observability-stack.ps1
```

The verifier starts the observability profile on disposable host ports, checks the baseline endpoints, confirms Grafana provisioned the Prometheus and Loki datasources, confirms the baseline dashboard exists, and then tears the stack back down.
