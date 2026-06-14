<#
  Reproducible Cloud Monitoring setup for good-news.

  Creates: log-based metrics, the dashboard (infra/monitoring/dashboard.json),
  an email notification channel, and alert policies. Idempotent: existing
  objects (matched by name / displayName) are skipped.

  Usage:
    .\infra\monitoring\apply.ps1 -AlertEmail you@example.com
#>
param(
  [string]$Project = "good-news-am26",
  [string]$Service = "good-news-app",
  [string]$AlertEmail = "typelolpro@gmail.com"
)

$ErrorActionPreference = "Stop"
$token = gcloud auth print-access-token
$hdr = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json; charset=utf-8" }
$base = "resource.type=`"cloud_run_revision`" AND resource.labels.service_name=`"$Service`""

# --- 1. Log-based metrics -------------------------------------------------
$metrics = @{
  good_news_analysis_failed     = "$base AND jsonPayload.event=`"analysis_failed`""
  good_news_source_sync_failed  = "$base AND jsonPayload.event=`"source_sync_failed`""
  good_news_delivery_failed     = "$base AND jsonPayload.event=`"delivery_run`" AND jsonPayload.status=`"failed`""
  good_news_gemini_rate_limited = "$base AND jsonPayload.event=`"gemini_rate_limited`""
  good_news_scheduler_failed    = "resource.type=`"cloud_scheduler_job`" AND severity>=ERROR"
}
foreach ($name in $metrics.Keys) {
  try {
    gcloud logging metrics create $name --project=$Project --description="good-news $name" --log-filter=$metrics[$name] 2>$null
    Write-Host "metric created: $name"
  } catch { Write-Host "metric exists: $name" }
}

# --- 2. Dashboard ---------------------------------------------------------
$existing = (Invoke-RestMethod -Method Get -Uri "https://monitoring.googleapis.com/v1/projects/$Project/dashboards" -Headers $hdr).dashboards
if ($existing | Where-Object { $_.displayName -eq "Good News - System & Processes" }) {
  Write-Host "dashboard exists"
} else {
  $bytes = [System.IO.File]::ReadAllBytes("$PSScriptRoot\dashboard.json")
  $d = Invoke-RestMethod -Method Post -Uri "https://monitoring.googleapis.com/v1/projects/$Project/dashboards" -Headers $hdr -Body $bytes
  Write-Host "dashboard created: $($d.name)"
}

# --- 3. Email notification channel ---------------------------------------
$channels = (Invoke-RestMethod -Method Get -Uri "https://monitoring.googleapis.com/v3/projects/$Project/notificationChannels" -Headers $hdr).notificationChannels
$chan = $channels | Where-Object { $_.type -eq "email" -and $_.labels.email_address -eq $AlertEmail } | Select-Object -First 1
if ($chan) {
  $chanName = $chan.name; Write-Host "channel exists: $chanName"
} else {
  $body = (@{ type="email"; displayName="good-news alerts (email)"; labels=@{ email_address=$AlertEmail } } | ConvertTo-Json)
  $chan = Invoke-RestMethod -Method Post -Uri "https://monitoring.googleapis.com/v3/projects/$Project/notificationChannels" -Headers $hdr -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
  $chanName = $chan.name; Write-Host "channel created: $chanName"
}

# --- 4. Alert policies ----------------------------------------------------
$existingPolicies = (Invoke-RestMethod -Method Get -Uri "https://monitoring.googleapis.com/v3/projects/$Project/alertPolicies" -Headers $hdr).alertPolicies
function Add-Policy($displayName, $condDisplay, $filter, $period, $threshold) {
  if ($existingPolicies | Where-Object { $_.displayName -eq $displayName }) { Write-Host "policy exists: $displayName"; return }
  $obj = @{ displayName=$displayName; combiner="OR"; notificationChannels=@($chanName); alertStrategy=@{ autoClose="604800s" };
    conditions=@(@{ displayName=$condDisplay; conditionThreshold=@{
      filter=$filter;
      aggregations=@(@{ alignmentPeriod=$period; perSeriesAligner="ALIGN_DELTA"; crossSeriesReducer="REDUCE_SUM" });
      comparison="COMPARISON_GT"; thresholdValue=$threshold; duration="0s"; trigger=@{ count=1 } } }) }
  $bytes = [System.Text.Encoding]::UTF8.GetBytes(($obj | ConvertTo-Json -Depth 12))
  $r = Invoke-RestMethod -Method Post -Uri "https://monitoring.googleapis.com/v3/projects/$Project/alertPolicies" -Headers $hdr -Body $bytes
  Write-Host "policy created: $($r.displayName)"
}

Add-Policy "good-news: Cloud Run 5xx errors" "5xx responses present" `
  "metric.type=`"run.googleapis.com/request_count`" resource.type=`"cloud_run_revision`" resource.label.`"service_name`"=`"$Service`" metric.label.`"response_code_class`"=`"5xx`"" "300s" 0
Add-Policy "good-news: Cloud Scheduler job failing" "scheduler job error" `
  "metric.type=`"logging.googleapis.com/user/good_news_scheduler_failed`" resource.type=`"cloud_scheduler_job`"" "600s" 0
Add-Policy "good-news: analysis failures spiking" "analysis_failed > 20 / hour" `
  "metric.type=`"logging.googleapis.com/user/good_news_analysis_failed`" resource.type=`"cloud_run_revision`"" "3600s" 20

Write-Host "done."
