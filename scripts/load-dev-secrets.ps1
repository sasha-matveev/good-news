param(
    [string]$SecretsFilePath = "",
    [string]$ComposeProjectName = "good-news"
)

$ErrorActionPreference = "Stop"

$script:GoodNewsCredentialTargets = @{
    GOOD_NEWS_APP_MASTER_KEY = "good-news/dev/app-master-key"
    GOOD_NEWS_POSTGRES_PASSWORD = "good-news/dev/postgres-password"
}
$script:GoodNewsRuntimeRecoveryServices = @(
    "content-api-service",
    "source-ingestion-service",
    "analysis-llm-service",
    "delivery-service",
    "postgres"
)

function Resolve-GoodNewsLocalSecretsFile {
    param(
        [string]$ExplicitPath
    )

    if ($ExplicitPath) {
        return [pscustomobject]@{
            Path = $ExplicitPath
            IsExplicit = $true
        }
    }

    if ($env:GOOD_NEWS_LOCAL_SECRETS_FILE) {
        return [pscustomobject]@{
            Path = $env:GOOD_NEWS_LOCAL_SECRETS_FILE
            IsExplicit = $true
        }
    }

    $homeDirectory = [Environment]::GetFolderPath("UserProfile")
    if (-not $homeDirectory) {
        return [pscustomobject]@{
            Path = ""
            IsExplicit = $false
        }
    }

    return [pscustomobject]@{
        Path = (Join-Path $homeDirectory ".good-news\dev-secrets.env")
        IsExplicit = $false
    }
}

function Get-GoodNewsCurrentIdentity {
    try {
        return [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    } catch {
        return [Environment]::UserName
    }
}

function Get-GoodNewsSecretLoadDiagnosticReport {
    param(
        [string]$ResolvedSecretsFilePath = "",
        [bool]$ResolvedSecretsFileIsExplicit = $false,
        [string[]]$AdditionalNotes = @()
    )

    $resolvedSecretsFile = if ($ResolvedSecretsFilePath) {
        [pscustomobject]@{
            Path = $ResolvedSecretsFilePath
            IsExplicit = $ResolvedSecretsFileIsExplicit
        }
    } else {
        Resolve-GoodNewsLocalSecretsFile -ExplicitPath $SecretsFilePath
    }

    $homeEnvironmentValue = if ($env:HOME) { $env:HOME } else { "<unset>" }
    $userProfileEnvironmentValue = if ($env:USERPROFILE) { $env:USERPROFILE } else { "<unset>" }
    $goodNewsLocalSecretsOverride = if ($env:GOOD_NEWS_LOCAL_SECRETS_FILE) { $env:GOOD_NEWS_LOCAL_SECRETS_FILE } else { "<unset>" }
    $resolvedSecretsFilePathText = if ($resolvedSecretsFile.Path) { $resolvedSecretsFile.Path } else { "<none>" }
    $resolvedSecretsFileExists = if ($resolvedSecretsFile.Path) { Test-Path -LiteralPath $resolvedSecretsFile.Path } else { $false }
    $resolvedSecretsFileExistsText = if ($resolvedSecretsFileExists) { "yes" } else { "no" }
    $resolvedSecretsFileExplicitText = if ($resolvedSecretsFile.IsExplicit) { "yes" } else { "no" }
    $credentialManagerLoaded = [bool](Get-Command -Name Test-GoodNewsCredentialExists -ErrorAction SilentlyContinue)
    $dockerCommandAvailableText = if (Get-Command -Name docker -ErrorAction SilentlyContinue) { "yes" } else { "no" }

    $lines = @(
        "Current execution context:"
        "  Windows identity: $(Get-GoodNewsCurrentIdentity)"
        "  HOME: $homeEnvironmentValue"
        "  USERPROFILE: $userProfileEnvironmentValue"
        "  GOOD_NEWS_LOCAL_SECRETS_FILE: $goodNewsLocalSecretsOverride"
        "  Resolved secrets file path: $resolvedSecretsFilePathText"
        "  Resolved secrets file explicit override: $resolvedSecretsFileExplicitText"
        "  Resolved secrets file exists: $resolvedSecretsFileExistsText"
        "  Runtime project fallback compose project: $ComposeProjectName"
        "  Docker command available for runtime fallback: $dockerCommandAvailableText"
        "  Windows Credential Manager is per-user. If this script is running under a different Windows user, agent account, or sandbox identity, it may see a different store."
        "  Credential targets checked:"
    )

    foreach ($entry in $script:GoodNewsCredentialTargets.GetEnumerator()) {
        $targetExistsText = "not checked"
        if ($credentialManagerLoaded) {
            $targetExistsText = if (Test-GoodNewsCredentialExists -TargetName $entry.Value) { "yes" } else { "no" }
        }

        $lines += "    $($entry.Key): $($entry.Value) (Credential Manager entry present: $targetExistsText)"
    }

    if ($AdditionalNotes.Count -gt 0) {
        $lines += "  Additional secret source notes:"
        foreach ($note in $AdditionalNotes) {
            $lines += "    $note"
        }
    }

    return ($lines -join [Environment]::NewLine)
}

function Import-GoodNewsDotenvSecrets {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $name = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1)
        if (
            ($value.Length -ge 2) -and (
                (($value.StartsWith('"')) -and ($value.EndsWith('"'))) -or
                (($value.StartsWith("'")) -and ($value.EndsWith("'")))
            )
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        if (($name -in @("GOOD_NEWS_APP_MASTER_KEY", "GOOD_NEWS_POSTGRES_PASSWORD")) -and (-not (Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue))) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

function Test-GoodNewsRequiredSecretsLoaded {
    return [bool]$env:GOOD_NEWS_APP_MASTER_KEY -and [bool]$env:GOOD_NEWS_POSTGRES_PASSWORD
}

function Set-GoodNewsComposePasswordMirror {
    if (-not $env:POSTGRES_PASSWORD) {
        $env:POSTGRES_PASSWORD = $env:GOOD_NEWS_POSTGRES_PASSWORD
    }
}

function Set-GoodNewsSecretFromCredentialIfMissing {
    param(
        [Parameter(Mandatory)]
        [string]$EnvName,
        [Parameter(Mandatory)]
        [string]$TargetName
    )

    if ((-not (Get-Item -Path "Env:$EnvName" -ErrorAction SilentlyContinue)) -and (Test-GoodNewsCredentialExists -TargetName $TargetName)) {
        Set-Item -Path "Env:$EnvName" -Value (Get-GoodNewsCredentialValue -TargetName $TargetName)
    }
}

function Get-GoodNewsRuntimeRecoveryContainerId {
    param(
        [Parameter(Mandatory)]
        [string]$ProjectName,
        [Parameter(Mandatory)]
        [string]$ServiceName
    )

    $dockerCommand = Get-Command -Name docker -ErrorAction SilentlyContinue
    if (-not $dockerCommand) {
        return ""
    }

    try {
        $containerIds = & docker ps --all `
            --filter "label=com.docker.compose.project=$ProjectName" `
            --filter "label=com.docker.compose.service=$ServiceName" `
            --format "{{.ID}}"
        if (($dockerCommand.CommandType -eq "Application") -and ($LASTEXITCODE -ne 0)) {
            return ""
        }
        if (-not $?) {
            return ""
        }

        foreach ($containerId in @($containerIds)) {
            $trimmedContainerId = ([string]$containerId).Trim()
            if ($trimmedContainerId) {
                return $trimmedContainerId
            }
        }
    } catch {
        return ""
    }

    return ""
}

function Get-GoodNewsContainerEnvironmentMap {
    param(
        [Parameter(Mandatory)]
        [string]$ContainerId
    )

    if (-not $ContainerId) {
        return @{}
    }

    $dockerCommand = Get-Command -Name docker -ErrorAction SilentlyContinue
    if (-not $dockerCommand) {
        return @{}
    }

    try {
        $environmentLines = & docker inspect --format "{{range .Config.Env}}{{println .}}{{end}}" $ContainerId
        if (($dockerCommand.CommandType -eq "Application") -and ($LASTEXITCODE -ne 0)) {
            return @{}
        }
        if (-not $?) {
            return @{}
        }
    } catch {
        return @{}
    }

    $environmentMap = @{}
    foreach ($environmentLine in @($environmentLines)) {
        $lineText = [string]$environmentLine
        $separatorIndex = $lineText.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $environmentName = $lineText.Substring(0, $separatorIndex)
        $environmentValue = $lineText.Substring($separatorIndex + 1)
        $environmentMap[$environmentName] = $environmentValue
    }

    return $environmentMap
}

function Set-GoodNewsSecretFromRuntimeProjectIfMissing {
    param(
        [Parameter(Mandatory)]
        [string]$ProjectName
    )

    $recoveredAnySecret = $false

    foreach ($serviceName in $script:GoodNewsRuntimeRecoveryServices) {
        if (Test-GoodNewsRequiredSecretsLoaded) {
            break
        }

        $containerId = Get-GoodNewsRuntimeRecoveryContainerId -ProjectName $ProjectName -ServiceName $serviceName
        if (-not $containerId) {
            continue
        }

        $containerEnvironment = Get-GoodNewsContainerEnvironmentMap -ContainerId $containerId
        if (($containerEnvironment.Count -eq 0) -and (-not $containerEnvironment.ContainsKey("GOOD_NEWS_APP_MASTER_KEY")) -and (-not $containerEnvironment.ContainsKey("GOOD_NEWS_POSTGRES_PASSWORD")) -and (-not $containerEnvironment.ContainsKey("POSTGRES_PASSWORD"))) {
            continue
        }

        if (
            (-not (Get-Item -Path "Env:GOOD_NEWS_APP_MASTER_KEY" -ErrorAction SilentlyContinue)) -and
            $containerEnvironment.ContainsKey("GOOD_NEWS_APP_MASTER_KEY")
        ) {
            Set-Item -Path "Env:GOOD_NEWS_APP_MASTER_KEY" -Value $containerEnvironment["GOOD_NEWS_APP_MASTER_KEY"]
            $recoveredAnySecret = $true
        }

        if (-not (Get-Item -Path "Env:GOOD_NEWS_POSTGRES_PASSWORD" -ErrorAction SilentlyContinue)) {
            if ($containerEnvironment.ContainsKey("GOOD_NEWS_POSTGRES_PASSWORD")) {
                Set-Item -Path "Env:GOOD_NEWS_POSTGRES_PASSWORD" -Value $containerEnvironment["GOOD_NEWS_POSTGRES_PASSWORD"]
                $recoveredAnySecret = $true
            } elseif ($containerEnvironment.ContainsKey("POSTGRES_PASSWORD")) {
                Set-Item -Path "Env:GOOD_NEWS_POSTGRES_PASSWORD" -Value $containerEnvironment["POSTGRES_PASSWORD"]
                $recoveredAnySecret = $true
            }
        }
    }

    return $recoveredAnySecret
}

if (Test-GoodNewsRequiredSecretsLoaded) {
    Set-GoodNewsComposePasswordMirror
    Write-Host "Loaded GOOD_NEWS_APP_MASTER_KEY: yes (pre-set)"
    Write-Host "Loaded GOOD_NEWS_POSTGRES_PASSWORD: yes (pre-set)"
    Write-Host "Loaded POSTGRES_PASSWORD: yes"
    return
}

$resolvedSecretsFile = Resolve-GoodNewsLocalSecretsFile -ExplicitPath $SecretsFilePath
$diagnosticNotes = @()
if ($resolvedSecretsFile.IsExplicit -and $resolvedSecretsFile.Path -and (-not (Test-Path -LiteralPath $resolvedSecretsFile.Path))) {
    $diagnosticNotes += "Explicit local secrets file '$($resolvedSecretsFile.Path)' was requested but does not exist."
    if ($env:GOOD_NEWS_LOCAL_SECRETS_FILE) {
        . "$PSScriptRoot\credential-manager.ps1"
        $diagnosticReport = Get-GoodNewsSecretLoadDiagnosticReport `
            -ResolvedSecretsFilePath $resolvedSecretsFile.Path `
            -ResolvedSecretsFileIsExplicit $resolvedSecretsFile.IsExplicit `
            -AdditionalNotes $diagnosticNotes
        throw "Explicit local secrets file '$($resolvedSecretsFile.Path)' was requested but does not exist.`n$diagnosticReport"
    }
}

if ($resolvedSecretsFile.Path -and (Test-Path -LiteralPath $resolvedSecretsFile.Path)) {
    Import-GoodNewsDotenvSecrets -Path $resolvedSecretsFile.Path
    if (Test-GoodNewsRequiredSecretsLoaded) {
        Set-GoodNewsComposePasswordMirror
        Write-Host "Loaded GOOD_NEWS_APP_MASTER_KEY: yes (from secrets file)"
        Write-Host "Loaded GOOD_NEWS_POSTGRES_PASSWORD: yes (from secrets file)"
        Write-Host "Loaded POSTGRES_PASSWORD: yes"
        return
    }

    $diagnosticNotes += "Secrets file '$($resolvedSecretsFile.Path)' did not fully define GOOD_NEWS_APP_MASTER_KEY and GOOD_NEWS_POSTGRES_PASSWORD."
}

. "$PSScriptRoot\credential-manager.ps1"

$appMasterKeyTarget = $script:GoodNewsCredentialTargets["GOOD_NEWS_APP_MASTER_KEY"]
$postgresPasswordTarget = $script:GoodNewsCredentialTargets["GOOD_NEWS_POSTGRES_PASSWORD"]
Set-GoodNewsSecretFromCredentialIfMissing -EnvName "GOOD_NEWS_APP_MASTER_KEY" -TargetName $appMasterKeyTarget
Set-GoodNewsSecretFromCredentialIfMissing -EnvName "GOOD_NEWS_POSTGRES_PASSWORD" -TargetName $postgresPasswordTarget

if (-not (Test-GoodNewsRequiredSecretsLoaded)) {
    $runtimeRecoverySucceeded = Set-GoodNewsSecretFromRuntimeProjectIfMissing -ProjectName $ComposeProjectName
    if ($runtimeRecoverySucceeded -and (Test-GoodNewsRequiredSecretsLoaded)) {
        Set-GoodNewsComposePasswordMirror
        Write-Host "Loaded GOOD_NEWS_APP_MASTER_KEY: yes (from runtime project container env)"
        Write-Host "Loaded GOOD_NEWS_POSTGRES_PASSWORD: yes (from runtime project container env)"
        Write-Host "Loaded POSTGRES_PASSWORD: yes"
        return
    }
}

if (-not (Test-GoodNewsRequiredSecretsLoaded)) {
    $diagnosticReport = Get-GoodNewsSecretLoadDiagnosticReport `
        -ResolvedSecretsFilePath $resolvedSecretsFile.Path `
        -ResolvedSecretsFileIsExplicit $resolvedSecretsFile.IsExplicit `
        -AdditionalNotes $diagnosticNotes
    throw "Required local secrets are still missing after checking pre-set environment variables, the resolved local secrets file, the current user's Windows Credential Manager store, and the selected runtime project's container environment.`n$diagnosticReport"
}

Set-GoodNewsComposePasswordMirror

Write-Host "Loaded GOOD_NEWS_APP_MASTER_KEY: yes (from Windows Credential Manager)"
Write-Host "Loaded GOOD_NEWS_POSTGRES_PASSWORD: yes (from Windows Credential Manager)"
Write-Host "Loaded POSTGRES_PASSWORD: yes"
