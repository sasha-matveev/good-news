param(
    [string]$OutputPath = ".env"
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\load-dev-secrets.ps1"

$resolvedOutputPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
} else {
    Join-Path (Get-Location) $OutputPath
}

if (-not $env:GOOD_NEWS_APP_MASTER_KEY -or -not $env:GOOD_NEWS_POSTGRES_PASSWORD) {
    throw "Secrets were not loaded. Ensure Windows Credential Manager entries exist or a secrets file is available."
}

$secretsToWrite = [ordered]@{
    GOOD_NEWS_APP_MASTER_KEY    = $env:GOOD_NEWS_APP_MASTER_KEY
    GOOD_NEWS_POSTGRES_PASSWORD = $env:GOOD_NEWS_POSTGRES_PASSWORD
    POSTGRES_PASSWORD           = $env:GOOD_NEWS_POSTGRES_PASSWORD
}

$existingLines = @()
if (Test-Path -LiteralPath $resolvedOutputPath) {
    $existingLines = Get-Content -LiteralPath $resolvedOutputPath
}

$updatedKeys = @{}
$outputLines = @()

foreach ($line in $existingLines) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        $outputLines += $line
        continue
    }
    $sep = $trimmed.IndexOf("=")
    if ($sep -lt 1) {
        $outputLines += $line
        continue
    }
    $key = $trimmed.Substring(0, $sep).Trim()
    if ($secretsToWrite.Contains($key)) {
        $outputLines += "$key=`"$($secretsToWrite[$key])`""
        $updatedKeys[$key] = $true
    } else {
        $outputLines += $line
    }
}

foreach ($entry in $secretsToWrite.GetEnumerator()) {
    if (-not $updatedKeys.ContainsKey($entry.Key)) {
        $outputLines += "$($entry.Key)=`"$($entry.Value)`""
    }
}

[System.IO.File]::WriteAllLines($resolvedOutputPath, $outputLines, [System.Text.Encoding]::UTF8)

Write-Host "Secrets exported to $resolvedOutputPath"
Write-Host "  GOOD_NEWS_APP_MASTER_KEY: set"
Write-Host "  GOOD_NEWS_POSTGRES_PASSWORD: set"
Write-Host "  POSTGRES_PASSWORD: set"
