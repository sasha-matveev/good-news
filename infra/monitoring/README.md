# Cloud Monitoring for Good News

Replaces the removed local Prometheus/Grafana stack with GCP-native observability.

## What's here

- **`dashboard.json`** — Cloud Monitoring dashboard "Good News - System & Processes":
  Cloud Run request rate / latency p95 / instances / cold-start latency / CPU / memory,
  Cloud Scheduler attempts by response code, and process events (analysis/sync/delivery
  failures, Gemini rate-limits).
- **`apply.ps1`** — idempotently creates the log-based metrics, dashboard, an email
  notification channel, and three alert policies.

## How metrics get there

Cloud Run infra metrics (requests, latency, instances, cold starts, CPU, memory) and
Cloud Scheduler metrics are emitted automatically by GCP — no app code needed.

Process/business metrics come from **structured log events**: the backend prints JSON
lines to stdout (`app/core/observability.py::emit_event`, e.g. `{"event":"analysis_failed",...}`),
Cloud Logging parses them into `jsonPayload`, and **log-based metrics** count them.
This survives Cloud Run cold starts, unlike the old in-process Prometheus counters
(which are kept only as a seam / for local use and are not scraped in production).

## Apply / re-apply

```powershell
.\infra\monitoring\apply.ps1 -AlertEmail you@example.com
```

Requires `gcloud auth login` with rights on project `good-news-am26`.

## Alerts

| Policy | Fires when |
|--------|-----------|
| Cloud Run 5xx errors | any 5xx response in a 5-min window |
| Cloud Scheduler job failing | a scheduler job logs an error (OIDC/4xx/5xx/timeout) |
| analysis failures spiking | >20 `analysis_failed` events in an hour |

Notifications go to the email notification channel created by `apply.ps1`.
Live dashboard: Cloud Console → Monitoring → Dashboards → "Good News - System & Processes".
