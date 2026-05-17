param(
    [string[]]$Services = @("all"),
    [string[]]$ComposeFiles = @("docker-compose.yml"),
    [string]$ComposeProjectName = "good-news",
    [string[]]$ComposeProfiles = @("ui", "ai")
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\validation\phase2-verification-common.ps1"

$resolvedServices = if ($Services.Count -eq 1 -and $Services[0].ToLowerInvariant() -eq "all") {
    @("postgres", "ollama", "app", "frontend")
} else {
    $Services
}

$restartArguments = @()
foreach ($profile in $ComposeProfiles) {
    $restartArguments += @("--profile", $profile)
}
$restartArguments += "restart"
$restartArguments += $resolvedServices

Invoke-GoodNewsCompose -ComposeFiles $ComposeFiles -ProjectName $ComposeProjectName -Arguments $restartArguments
