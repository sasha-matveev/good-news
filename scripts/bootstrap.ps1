param(
    [switch]$CheckSecrets,
    [switch]$RecreateVenv,
    [string]$AppMasterKey,
    [string]$PostgresPassword
)

$ErrorActionPreference = "Stop"

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Native command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Write-SecretStatus {
    param(
        [string]$Label,
        [bool]$Present
    )

    $status = if ($Present) { "yes" } else { "no" }
    Write-Host "${Label}: $status"
}

function Resolve-GoodNewsLocalSecretsFile {
    if ($env:GOOD_NEWS_LOCAL_SECRETS_FILE) {
        return $env:GOOD_NEWS_LOCAL_SECRETS_FILE
    }

    $homeDirectory = [Environment]::GetFolderPath("UserProfile")
    if (-not $homeDirectory) {
        return ""
    }

    return Join-Path $homeDirectory ".good-news\dev-secrets.env"
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

. "$PSScriptRoot\credential-manager.ps1"

$appMasterKeyTarget = "good-news/dev/app-master-key"
$postgresPasswordTarget = "good-news/dev/postgres-password"

if ($AppMasterKey) {
    Set-GoodNewsCredentialValue -TargetName $appMasterKeyTarget -Secret $AppMasterKey
}

if ($PostgresPassword) {
    Set-GoodNewsCredentialValue -TargetName $postgresPasswordTarget -Secret $PostgresPassword
}

if ($CheckSecrets) {
    $localSecretsFile = Resolve-GoodNewsLocalSecretsFile
    $currentIdentity = try { [System.Security.Principal.WindowsIdentity]::GetCurrent().Name } catch { [Environment]::UserName }
    $homeEnvironmentValue = if ($env:HOME) { $env:HOME } else { "<unset>" }
    $userProfileEnvironmentValue = if ($env:USERPROFILE) { $env:USERPROFILE } else { "<unset>" }
    $goodNewsLocalSecretsOverride = if ($env:GOOD_NEWS_LOCAL_SECRETS_FILE) { $env:GOOD_NEWS_LOCAL_SECRETS_FILE } else { "<unset>" }
    Write-Host "Current execution context:"
    Write-Host "  Windows identity: $currentIdentity"
    Write-Host "  HOME: $homeEnvironmentValue"
    Write-Host "  USERPROFILE: $userProfileEnvironmentValue"
    Write-Host "  GOOD_NEWS_LOCAL_SECRETS_FILE: $goodNewsLocalSecretsOverride"
    Write-Host "Platform-neutral local secrets file:"
    Write-SecretStatus -Label "  $localSecretsFile" -Present ([bool]$localSecretsFile -and (Test-Path -LiteralPath $localSecretsFile))
    Write-Host "Credential Manager entries present:"
    Write-SecretStatus -Label "  $appMasterKeyTarget" -Present (Test-GoodNewsCredentialExists -TargetName $appMasterKeyTarget)
    Write-SecretStatus -Label "  $postgresPasswordTarget" -Present (Test-GoodNewsCredentialExists -TargetName $postgresPasswordTarget)
    Write-Host "Windows Credential Manager is per-user. If operator and agent contexts differ, they can see different stores."
    Write-Host "Process-scoped environment variables loaded:"
    Write-SecretStatus -Label "  GOOD_NEWS_APP_MASTER_KEY" -Present ([bool]$env:GOOD_NEWS_APP_MASTER_KEY)
    Write-SecretStatus -Label "  GOOD_NEWS_POSTGRES_PASSWORD" -Present ([bool]$env:GOOD_NEWS_POSTGRES_PASSWORD)
    Write-SecretStatus -Label "  POSTGRES_PASSWORD" -Present ([bool]$env:POSTGRES_PASSWORD)
    return
}

if ($RecreateVenv -and (Test-Path .venv)) {
    Remove-Item -LiteralPath .venv -Recurse -Force
}

if (-not (Test-Path .venv)) {
    Invoke-NativeCommand -FilePath py -Arguments "-m", "venv", ".venv"
}

. .\.venv\Scripts\Activate.ps1
Invoke-NativeCommand -FilePath python -Arguments "-m", "pip", "install", "--upgrade", "pip"
Invoke-NativeCommand -FilePath python -Arguments "-m", "pip", "install", "-e", ".\backend[dev]"
Invoke-NativeCommand -FilePath npm -Arguments "install", "--prefix", "frontend"

Write-Host "Dependency bootstrap complete."
Write-Host "Supported local secret contract:"
Write-Host '  1. export GOOD_NEWS_APP_MASTER_KEY and GOOD_NEWS_POSTGRES_PASSWORD in your shell, or'
Write-Host '  2. write those keys to $HOME/.good-news/dev-secrets.env (or set GOOD_NEWS_LOCAL_SECRETS_FILE), or'
Write-Host '  3. optionally refresh the Windows Credential Manager convenience store with:'
Write-Host '  .\scripts\bootstrap.ps1 -AppMasterKey "<value>" -PostgresPassword "<value>"'
Write-Host "Load process-scoped secrets into the current shell before migrations or docker compose:"
Write-Host '  . .\scripts\load-dev-secrets.ps1'
Write-Host '  . .\scripts\load-dev-secrets.ps1 -SecretsFilePath "C:\path\outside\the\repo\dev-secrets.env"'
