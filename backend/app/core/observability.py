from __future__ import annotations

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

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


def record_analysis_failure(*, reason: str) -> None:
    ANALYSIS_FAILURES_TOTAL.labels(reason=reason).inc()


def record_delivery_run(*, digest_type: str, status: str) -> None:
    DELIVERY_RUNS_TOTAL.labels(digest_type=digest_type, status=status).inc()
