from __future__ import annotations

import json
import re
import sys
import time
import uuid

from fastapi import FastAPI, Request
from prometheus_client import Counter, Gauge, Histogram

BACKEND_HEADER = "X-Good-News-Backend"
CORRELATION_HEADER = "X-Correlation-ID"
BACKEND_IDENTITY = "python"
_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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
    ["backend", "service", "method", "route", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "good_news_http_request_duration_seconds",
    "HTTP request latency handled by Good News services.",
    ["backend", "service", "method", "route", "status"],
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
        started_at = time.perf_counter()
        correlation_id = _correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        status_code = 500
        error_type: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            duration_seconds = time.perf_counter() - started_at
            labels = {
                "backend": BACKEND_IDENTITY,
                "service": service_name,
                "method": request.method,
                "route": route_path,
                "status": str(status_code),
            }
            HTTP_REQUESTS_TOTAL.labels(**labels).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)
            emit_event(
                "http_request",
                severity="ERROR" if status_code >= 500 else "INFO",
                backend=BACKEND_IDENTITY,
                service=service_name,
                correlation_id=correlation_id,
                method=request.method,
                route=route_path,
                status=status_code,
                duration_ms=round(duration_seconds * 1000, 3),
                error_type=error_type,
            )

        response.headers[BACKEND_HEADER] = BACKEND_IDENTITY
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


def _correlation_id(candidate: str | None) -> str:
    normalized = (candidate or "").strip()
    if _CORRELATION_ID_PATTERN.fullmatch(normalized):
        return normalized
    return str(uuid.uuid4())


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
