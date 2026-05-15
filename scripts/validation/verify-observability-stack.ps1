param(
    [int]$StartupTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\phase2-verification-common.ps1"

Set-GoodNewsPhase2TestSecrets

$script:CurlCommand = Get-GoodNewsCurlCommand
$projectName = "observability-foundation-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$composeFiles = @("docker-compose.yml")
$observabilityServices = @("grafana", "prometheus", "loki", "otel-collector", "grafana-image-renderer")
$stackStarted = $false

function Invoke-ObservabilityCompose {
    param(
        [string[]]$Arguments
    )

    Invoke-GoodNewsCompose -ComposeFiles $composeFiles -ProjectName $projectName -Arguments $Arguments
}

function Wait-ForObservabilityHttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSeconds,
        [string]$Label
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            & $script:CurlCommand "-fsS" $Url *> $null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "$Label ready: $Url"
                return
            }
        } catch {
        }

        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for $Label at $Url"
}

function New-GrafanaAuthHeaders {
    $bytes = [System.Text.Encoding]::ASCII.GetBytes("admin:admin")
    $token = [Convert]::ToBase64String($bytes)
    return @{
        Authorization = "Basic $token"
    }
}

function Invoke-GrafanaJsonRequest {
    param(
        [string]$Url
    )

    return Invoke-RestMethod -Headers (New-GrafanaAuthHeaders) -Method "GET" -Uri $Url -ErrorAction "Stop"
}

try {
    Assert-GoodNewsDockerAccess

    if (-not $env:GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN) {
        $env:GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN = "http://127.0.0.1:8000"
    }

    if (-not $env:GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN) {
        $env:GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN = "http://127.0.0.1:5173"
    }

    $env:GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT = Get-GoodNewsAvailableTcpPort
    $env:GOOD_NEWS_OBSERVABILITY_PROMETHEUS_HOST_PORT = Get-GoodNewsAvailableTcpPort
    $env:GOOD_NEWS_OBSERVABILITY_LOKI_HOST_PORT = Get-GoodNewsAvailableTcpPort
    $env:GOOD_NEWS_OBSERVABILITY_OTEL_GRPC_HOST_PORT = Get-GoodNewsAvailableTcpPort
    $env:GOOD_NEWS_OBSERVABILITY_OTEL_HTTP_HOST_PORT = Get-GoodNewsAvailableTcpPort
    $env:GOOD_NEWS_OBSERVABILITY_OTEL_HEALTH_HOST_PORT = Get-GoodNewsAvailableTcpPort
    $env:GOOD_NEWS_OBSERVABILITY_OTEL_METRICS_HOST_PORT = Get-GoodNewsAvailableTcpPort
    $env:GOOD_NEWS_OBSERVABILITY_RENDERER_HOST_PORT = Get-GoodNewsAvailableTcpPort

    $grafanaBaseUrl = "http://127.0.0.1:$($env:GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT)"
    $prometheusBaseUrl = "http://127.0.0.1:$($env:GOOD_NEWS_OBSERVABILITY_PROMETHEUS_HOST_PORT)"
    $lokiBaseUrl = "http://127.0.0.1:$($env:GOOD_NEWS_OBSERVABILITY_LOKI_HOST_PORT)"
    $otelHealthUrl = "http://127.0.0.1:$($env:GOOD_NEWS_OBSERVABILITY_OTEL_HEALTH_HOST_PORT)/"
    $rendererBaseUrl = "http://127.0.0.1:$($env:GOOD_NEWS_OBSERVABILITY_RENDERER_HOST_PORT)"

    Write-Host "Booting local observability foundation stack..."
    Invoke-ObservabilityCompose -Arguments (@(
        "--profile",
        "observability",
        "up",
        "-d"
    ) + $observabilityServices)
    $stackStarted = $true

    Wait-ForObservabilityHttpOk -Url "$grafanaBaseUrl/api/health" -TimeoutSeconds $StartupTimeoutSeconds -Label "grafana"
    Wait-ForObservabilityHttpOk -Url "$prometheusBaseUrl/-/ready" -TimeoutSeconds $StartupTimeoutSeconds -Label "prometheus"
    Wait-ForObservabilityHttpOk -Url "$lokiBaseUrl/ready" -TimeoutSeconds $StartupTimeoutSeconds -Label "loki"
    Wait-ForObservabilityHttpOk -Url $otelHealthUrl -TimeoutSeconds $StartupTimeoutSeconds -Label "otel-collector"
    Wait-ForObservabilityHttpOk -Url "$rendererBaseUrl/metrics" -TimeoutSeconds $StartupTimeoutSeconds -Label "grafana-image-renderer"

    $prometheusDatasource = Invoke-GrafanaJsonRequest -Url "$grafanaBaseUrl/api/datasources/name/Prometheus"
    if ($prometheusDatasource.type -ne "prometheus") {
        throw "Grafana did not provision the Prometheus datasource."
    }

    $lokiDatasource = Invoke-GrafanaJsonRequest -Url "$grafanaBaseUrl/api/datasources/name/Loki"
    if ($lokiDatasource.type -ne "loki") {
        throw "Grafana did not provision the Loki datasource."
    }

    $dashboard = Invoke-GrafanaJsonRequest -Url "$grafanaBaseUrl/api/dashboards/uid/good-news-overview"
    if ($dashboard.dashboard.title -ne "Good News Observability Overview") {
        throw "Grafana did not provision the baseline dashboard."
    }

    $grafanaAlertRules = Invoke-GrafanaJsonRequest -Url "$grafanaBaseUrl/api/v1/provisioning/alert-rules"
    if (-not ($grafanaAlertRules.uid -contains "good-news-content-api-down")) {
        throw "Grafana did not provision the Good News alert rules."
    }

    $rulesResponse = Invoke-RestMethod -Method "GET" -Uri "$prometheusBaseUrl/api/v1/rules" -ErrorAction "Stop"
    $ruleNames = @($rulesResponse.data.groups.rules | ForEach-Object { $_.name })
    if (-not ($ruleNames -contains "GoodNewsContentApiDown")) {
        throw "Prometheus did not load the Good News alert rules."
    }

    Invoke-ObservabilityCompose -Arguments @(
        "--profile",
        "observability",
        "ps"
    )

    Write-Host ""
    Write-Host "Observability foundation verification passed."
    Write-Host "Grafana: $grafanaBaseUrl"
    Write-Host "Prometheus: $prometheusBaseUrl"
    Write-Host "Loki: $lokiBaseUrl"
    Write-Host "OTel health: $otelHealthUrl"
    Write-Host "Renderer metrics: $rendererBaseUrl/metrics"
} finally {
    if ($stackStarted) {
        Invoke-ObservabilityCompose -Arguments @(
            "--profile",
            "observability",
            "down",
            "-v",
            "--remove-orphans"
        )
    }
}
