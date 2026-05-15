<#
.SYNOPSIS
    Build, test, and deploy the Good News stack locally in Docker.

.DESCRIPTION
    Single operator entrypoint for the supported local deploy flow:
      1. Load secrets (Credential Manager -> dotenv file -> pre-set env).
      2. Run backend and frontend quality gates.
      3. Build and start the Docker stack under the project name "good-news".
      4. Wait for the frontend to respond before reporting success.

    Secrets are loaded via scripts\load-dev-secrets.ps1.
    Docker project name is always "good-news" (matches docker compose default
    for this repo root, eliminating the previous good-news-runtime mismatch).

.PARAMETER SecretsFilePath
    Optional explicit path to a .env-style secrets file.
    Forwarded to load-dev-secrets.ps1.

.PARAMETER StartupTimeoutSeconds
    How long to wait for services to become healthy. Default: 150.

.PARAMETER SkipTests
    Skip backend and frontend quality gates. Use only for config-only redeploys.
#>
param(
    [string]$SecretsFilePath = "",
    [int]$StartupTimeoutSeconds = 150,
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ProjectName = "good-news"
$script:ComposeFiles = @((Join-Path (Split-Path -Parent $PSScriptRoot) "docker-compose.yml"))

# ---------------------------------------------------------------------------
# Load helpers and secrets
# ---------------------------------------------------------------------------

. "$PSScriptRoot\validation\phase2-verification-common.ps1"
. "$PSScriptRoot\load-dev-secrets.ps1" `
    -SecretsFilePath $SecretsFilePath `
    -ComposeProjectName $script:ProjectName

# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "=== QUALITY GATE: backend tests ==="
    $pythonCommand = Get-GoodNewsPythonCommand
    & $pythonCommand -m pytest `
        backend/tests/unit/test_analysis_service_client.py `
        backend/tests/unit/test_source_ingestion_service_client.py `
        backend/tests/unit/test_task_two_runtime_contract.py `
        backend/tests/unit/test_task_four_runtime_contract.py `
        backend/tests/unit/test_task_five_runtime_contract.py `
        backend/tests/unit/test_phase_three_runtime_contract.py `
        backend/tests/unit/test_phase_four_runtime_contract.py `
        backend/tests/unit/test_performance_runtime_contract.py `
        backend/tests/contract `
        -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Backend tests failed. Deploy aborted."
        exit 1
    }

    Write-Host ""
    Write-Host "=== QUALITY GATE: frontend tests ==="
    npm --prefix frontend run test
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Frontend tests failed. Deploy aborted."
        exit 1
    }

    Write-Host ""
    Write-Host "=== QUALITY GATE: frontend build ==="
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Frontend build failed. Deploy aborted."
        exit 1
    }
} else {
    Write-Host "WARNING: Quality gates skipped (-SkipTests). Only use for config-only redeploys."
}

# ---------------------------------------------------------------------------
# Resolve port-dependent public origins
# ---------------------------------------------------------------------------

$contentApiPort = if ($env:GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT) {
    [int]$env:GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT
} else { 8000 }

$frontendPort = if ($env:GOOD_NEWS_FRONTEND_HOST_PORT) {
    [int]$env:GOOD_NEWS_FRONTEND_HOST_PORT
} else { 5173 }

if (-not $env:GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN) {
    $env:GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN = "http://127.0.0.1:$contentApiPort"
}
if (-not $env:GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN) {
    $env:GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN = "http://127.0.0.1:$frontendPort"
}

# ---------------------------------------------------------------------------
# Resolve Ollama config
# ---------------------------------------------------------------------------

$ollamaModel = if ($env:GOOD_NEWS_OLLAMA_MODEL) { $env:GOOD_NEWS_OLLAMA_MODEL } `
               else { "llama3.2:3b-instruct-q4_K_M" }
$useOllama = -not $env:GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON

# ---------------------------------------------------------------------------
# Boot postgres
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== DOCKER: starting postgres ==="
Invoke-GoodNewsDockerCompose `
    -ComposeFiles $script:ComposeFiles `
    -ProjectName $script:ProjectName `
    -Arguments @("up", "-d", "--build", "postgres")

Wait-ForGoodNewsPostgres `
    -ComposeFiles $script:ComposeFiles `
    -ProjectName $script:ProjectName `
    -TimeoutSeconds $StartupTimeoutSeconds

# ---------------------------------------------------------------------------
# Run database migrations
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== DOCKER: running db-migrate ==="
Invoke-GoodNewsDockerCompose `
    -ComposeFiles $script:ComposeFiles `
    -ProjectName $script:ProjectName `
    -Arguments @("--profile", "migration", "run", "--rm", "--no-deps", "db-migrate")

# ---------------------------------------------------------------------------
# Ollama bootstrap
# ---------------------------------------------------------------------------

if ($useOllama) {
    Write-Host ""
    Write-Host "=== DOCKER: starting ollama ==="
    Invoke-GoodNewsDockerCompose `
        -ComposeFiles $script:ComposeFiles `
        -ProjectName $script:ProjectName `
        -Arguments @("--profile", "ai", "up", "-d", "ollama")

    Ensure-GoodNewsOllamaModel `
        -ComposeFiles $script:ComposeFiles `
        -ProjectName $script:ProjectName `
        -Model $ollamaModel `
        -TimeoutSeconds $StartupTimeoutSeconds
}

# ---------------------------------------------------------------------------
# Start application services
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== DOCKER: starting application services ==="

$profileArgs = @("--profile", "ui")
if ($useOllama) { $profileArgs += @("--profile", "ai") }

Invoke-GoodNewsDockerCompose `
    -ComposeFiles $script:ComposeFiles `
    -ProjectName $script:ProjectName `
    -Arguments ($profileArgs + @(
        "up", "-d", "--build",
        "analysis-llm-service",
        "source-ingestion-service",
        "delivery-service",
        "content-api-service",
        "frontend",
        "prometheus",
        "loki",
        "otel-collector",
        "grafana-image-renderer",
        "grafana"
    ))

# ---------------------------------------------------------------------------
# Wait for frontend and Grafana health
# ---------------------------------------------------------------------------

$grafanaPort = if ($env:GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT) {
    [int]$env:GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT
} else { 3000 }

Wait-ForGoodNewsHttpOk `
    -Url "http://127.0.0.1:$frontendPort" `
    -TimeoutSeconds $StartupTimeoutSeconds `
    -Label "frontend"

Wait-ForGoodNewsHttpOk `
    -Url "http://127.0.0.1:$grafanaPort/api/health" `
    -TimeoutSeconds $StartupTimeoutSeconds `
    -Label "grafana"

Write-Host ""
Write-Host "=== Deploy complete ==="
Write-Host "  Frontend:       http://127.0.0.1:$frontendPort"
Write-Host "  Content API:    http://127.0.0.1:$contentApiPort/api/health"
Write-Host "  Grafana:        http://127.0.0.1:$grafanaPort"
Write-Host "  Docker project: $($script:ProjectName)"
Write-Host ""
Write-Host "Run 'docker compose -p $($script:ProjectName) ps' to inspect service state."
