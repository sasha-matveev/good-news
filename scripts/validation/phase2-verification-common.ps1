$ErrorActionPreference = "Stop"

function Get-GoodNewsPythonCommand {
    $candidates = @(
        (Join-Path $PWD ".venv\Scripts\python.exe"),
        (Join-Path $PWD ".venv/bin/python"),
        "python"
    )

    foreach ($candidate in $candidates) {
        if (($candidate -eq "python") -or (Test-Path $candidate)) {
            return $candidate
        }
    }

    throw "Could not resolve a Python executable."
}

function Get-GoodNewsCurlCommand {
    foreach ($candidate in @("curl.exe", "curl")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            return $candidate
        }
    }

    throw "Could not resolve a curl executable."
}

function Get-GoodNewsAvailableTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    } finally {
        $listener.Stop()
    }
}

function Set-GoodNewsPhase2TestSecrets {
    if (-not $env:GOOD_NEWS_APP_MASTER_KEY) {
        $env:GOOD_NEWS_APP_MASTER_KEY = "phase2-test-master-key"
    }

    if (-not $env:GOOD_NEWS_POSTGRES_PASSWORD) {
        $env:GOOD_NEWS_POSTGRES_PASSWORD = "phase2-test-postgres-password"
    }

    if (-not $env:POSTGRES_PASSWORD) {
        $env:POSTGRES_PASSWORD = $env:GOOD_NEWS_POSTGRES_PASSWORD
    }
}

function Invoke-GoodNewsDockerCompose {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName,
        [string[]]$Arguments
    )

    $dockerArguments = @("compose")
    foreach ($composeFile in $ComposeFiles) {
        $dockerArguments += @("-f", $composeFile)
    }
    $dockerArguments += @("-p", $ProjectName)
    $dockerArguments += $Arguments

    # PowerShell 5.1 converts native-exe stderr to ErrorRecord objects.
    # Set EAP to Continue so docker progress lines don't terminate the script.
    # Tee output: stream to host in real time AND accumulate for reprint on failure.
    $allLines = [System.Collections.Generic.List[string]]::new()
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker @dockerArguments 2>&1 | ForEach-Object {
        $str = [string]$_
        Write-Host $str
        $allLines.Add($str)
    }
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP

    if ($exitCode -ne 0) {
        Write-Host ""
        Write-Host "ERROR: docker compose exited with code $exitCode"
        Write-Host "Command: docker $($dockerArguments -join ' ')"
        Write-Host "--- Last 30 lines (may contain the docker error) ---"
        $allLines | Select-Object -Last 30 | ForEach-Object { Write-Host $_ }
        Write-Host "----------------------------------------------------"
        throw "docker compose failed (exit $exitCode): $($Arguments -join ' ')"
    }
}

# Backward-compat alias — validation scripts call Invoke-GoodNewsCompose unchanged.
function Invoke-GoodNewsCompose {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName,
        [string[]]$Arguments
    )
    Invoke-GoodNewsDockerCompose -ComposeFiles $ComposeFiles -ProjectName $ProjectName -Arguments $Arguments
}

function Assert-GoodNewsDockerAccess {
    try {
        & docker context inspect desktop-linux *> $null
    } catch {
    }

    $linuxPipePresent = Test-Path "\\.\pipe\dockerDesktopLinuxEngine"
    $defaultPipePresent = Test-Path "\\.\pipe\docker_engine"
    if (-not $linuxPipePresent -and -not $defaultPipePresent) {
        throw "Docker is not available: neither dockerDesktopLinuxEngine nor docker_engine pipe is present."
    }

    & docker version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is installed but the current shell cannot access the Docker API."
    }
}

function Invoke-GoodNewsDatabaseMigration {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName
    )

    Invoke-GoodNewsCompose -ComposeFiles $ComposeFiles -ProjectName $ProjectName -Arguments @(
        "--profile",
        "migration",
        "run",
        "--rm",
        "--no-deps",
        "db-migrate"
    )
}

function Wait-ForGoodNewsHttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSeconds,
        [string]$Label
    )

    $curlCommand = Get-GoodNewsCurlCommand
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            & $curlCommand "-fsS" $Url *> $null
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

function Wait-ForGoodNewsPostgres {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            Invoke-GoodNewsCompose -ComposeFiles $ComposeFiles -ProjectName $ProjectName -Arguments @(
                "exec",
                "-T",
                "postgres",
                "pg_isready",
                "-U",
                "good_news",
                "-d",
                "good_news"
            )
            return
        } catch {
        }

        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for postgres in project $ProjectName."
}

function Wait-ForGoodNewsOllama {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            Invoke-GoodNewsCompose -ComposeFiles $ComposeFiles -ProjectName $ProjectName -Arguments @(
                "exec",
                "-T",
                "ollama",
                "ollama",
                "list"
            )
            return
        } catch {
        }

        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for ollama in project $ProjectName."
}

function Test-GoodNewsOllamaModelPresent {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName,
        [string]$Model
    )

    try {
        $dockerArguments = @("compose")
        foreach ($composeFile in $ComposeFiles) {
            $dockerArguments += @("-f", $composeFile)
        }
        $dockerArguments += @("-p", $ProjectName, "exec", "-T", "ollama", "ollama", "list")
        $modelList = & docker @dockerArguments
        if ($LASTEXITCODE -ne 0) {
            return $false
        }

        $escapedModel = [regex]::Escape($Model)
        return (($modelList -join "`n") -match "(?m)^$escapedModel(\s|$)")
    } catch {
        return $false
    }
}

function Ensure-GoodNewsOllamaModel {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName,
        [string]$Model,
        [int]$TimeoutSeconds = 600
    )

    Invoke-GoodNewsCompose -ComposeFiles $ComposeFiles -ProjectName $ProjectName -Arguments @(
        "--profile",
        "ai",
        "up",
        "-d",
        "ollama"
    )

    Wait-ForGoodNewsOllama -ComposeFiles $ComposeFiles -ProjectName $ProjectName -TimeoutSeconds $TimeoutSeconds

    if (Test-GoodNewsOllamaModelPresent -ComposeFiles $ComposeFiles -ProjectName $ProjectName -Model $Model) {
        Write-Host "Ollama model already present: $Model"
        return
    }

    Write-Host "Pulling Ollama model $Model"
    Invoke-GoodNewsCompose -ComposeFiles $ComposeFiles -ProjectName $ProjectName -Arguments @(
        "exec",
        "-T",
        "ollama",
        "ollama",
        "pull",
        $Model
    )
}

function Test-GoodNewsAppShellHtml {
    param(
        [AllowNull()]
        [AllowEmptyCollection()]
        [object[]]$Html
    )

    if ($null -eq $Html -or $Html.Count -eq 0) {
        return $false
    }

    $joinedHtml = ($Html | ForEach-Object { [string]$_ }) -join "`n"
    return ($joinedHtml -match "<!doctype html>") -and ($joinedHtml -match '<div id="root"></div>')
}
