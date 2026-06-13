from __future__ import annotations

import json
import sys

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest


def emit_event(event: str, *, severity: str = "INFO", **fields: object) -> None:
    """Write a structured JSON event line to stdout.

    On Cloud Run this is parsed by Cloud Logging into ``jsonPayload``, which
    lets us build log-based metrics (counters/labels) that survive cold starts —
    unlike the in-memory Prometheus counters below, which reset per instance and
    are never scraped in a scale-to-zero deployment. The Prometheus counters are
    kept for local/standalone use and as a structured-logging seam.
    """
    payload: dict[str, object] = {"severity": severity, "event": event, **fields}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stdout, flush=True)

HTTP_REQUESTS_TOTAL = Counter(
    "good_news_http_requests_total",
    "HTTP requests handled by Good News services.",
    ["service", "method", "route", "status"],
)
SOURCE_SYNC_FAILURES_TOTAL = Counter(
    "good_news_source_sync_failures_total",
    "Source-sync failures that require operator attention.",
    ["event_code"],
)
ANALYSIS_FAILURES_TOTAL = Counter(
    "good_news_analysis_failures_total",
    "Analysis write failures recorded during source sync.",
    ["reason"],
)
DELIVERY_RUNS_TOTAL = Counter(
    "good_news_delivery_runs_total",
    "Digest and observability-report delivery runs by type and outcome.",
    ["digest_type", "status"],
)
SERVICE_UP = Gauge(
    "good_news_service_up",
    "Whether a Good News service process is currently serving metrics.",
    ["service"],
)


def instrument_app(*, app: FastAPI, service_name: str) -> None:
    SERVICE_UP.labels(service=service_name).set(1)

    @app.middleware("http")
    async def collect_request_metrics(request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS_TOTAL.labels(
            service=service_name,
            method=request.method,
            route=route_path,
            status=str(response.status_code),
        ).inc()
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_source_sync_failure(*, event_code: str) -> None:
    SOURCE_SYNC_FAILURES_TOTAL.labels(event_code=event_code).inc()
    emit_event("source_sync_failed", severity="WARNING", event_code=event_code)


def record_analysis_failure(*, reason: str) -> None:
    ANALYSIS_FAILURES_TOTAL.labels(reason=reason).inc()
    emit_event("analysis_failed", severity="WARNING", reason=reason)


def record_delivery_run(*, digest_type: str, status: str) -> None:
    DELIVERY_RUNS_TOTAL.labels(digest_type=digest_type, status=status).inc()
    severity = "WARNING" if status == "failed" else "INFO"
    emit_event("delivery_run", severity=severity, digest_type=digest_type, status=status)


def record_gemini_rate_limited(*, model: str, attempt: int) -> None:
    emit_event("gemini_rate_limited", severity="WARNING", model=model, attempt=attempt)
