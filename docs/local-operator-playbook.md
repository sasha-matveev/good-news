# Local Operator Playbook

Single reference for the supported local instance: start, restart, health, logs, stop, and recovery.

## Start (full deploy)

Required after any code change. Runs quality gates, builds images, migrates the database, and waits for all services to become healthy.

```powershell
.\scripts\deploy.ps1
```

With an explicit secrets file:

```powershell
.\scripts\deploy.ps1 -SecretsFilePath "C:\path\outside\the\repo\dev-secrets.env"
```

Skip quality gates for config-only redeploys only:

```powershell
.\scripts\deploy.ps1 -SkipTests
```

## Restart

Use when you need runtime recovery or config re-read without rebuilding images. Does **not** run tests or pick up code changes.

```powershell
# restart all default services
.\scripts\restart-runtime-service.ps1 -Services all

# restart a single service
.\scripts\restart-runtime-service.ps1 -Services app
```

## In-app monitoring

The **Monitoring tab** (http://127.0.0.1:5173/monitoring) is the primary in-app operator entry point. It shows source health, system health, LLM queue depth, capacity, and last sync time without leaving the browser.

## Health check

```powershell
docker compose -p good-news ps
curl http://127.0.0.1:8000/api/health
```

## Logs

```powershell
docker compose -p good-news logs -f app
docker compose -p good-news logs -f frontend
```

## Stop

```powershell
docker compose -p good-news down
```

## Secrets

Secrets are loaded by `scripts/load-dev-secrets.ps1` in this priority order:

1. Environment variables already set in the shell.
2. Dotenv file at the path given by `-SecretsFilePath` or `GOOD_NEWS_LOCAL_SECRETS_FILE`.
3. Windows Credential Manager fallback (per-user — operator and CI contexts may see different stores).

The `SecretsFilePath` parameter is accepted by `deploy.ps1` and `load-dev-secrets.ps1`.

## Docker project name

All commands use the project name `good-news`. Pass `-p good-news` to any manual `docker compose` invocation.
