param(
    [string]$Model = "llama3.2:3b-instruct-q4_K_M",
    [string]$SecretsFilePath = "",
    [string[]]$ComposeFiles = @("docker-compose.yml"),
    [string]$ComposeProjectName = "good-news"
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\validation\phase2-verification-common.ps1"
. .\scripts\load-dev-secrets.ps1 -SecretsFilePath $SecretsFilePath -ComposeProjectName $ComposeProjectName

Ensure-GoodNewsOllamaModel -ComposeFiles $ComposeFiles -ProjectName $ComposeProjectName -Model $Model
