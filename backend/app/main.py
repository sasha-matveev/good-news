from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.ai.ollama_client import OllamaClient
from app.api.routes.digests import router as digests_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.health import router as health_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.preferences import router as preferences_router
from app.api.routes.posts import router as posts_router
from app.api.routes.settings import router as settings_router
from app.api.routes.sources import router as sources_router
from app.api.routes.want_to_read import router as want_to_read_router
from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory
from app.core.observability import instrument_app
from app.core.schema_guard import assert_database_schema_is_current
from app.jobs.digest_jobs import (
    catch_up_daily_digest_if_needed,
    catch_up_daily_observability_report_if_needed,
    catch_up_weekly_digest_if_needed,
    register_daily_digest_job,
    register_daily_observability_report_job,
    register_weekly_digest_job,
    run_daily_digest,
    run_daily_observability_report,
    run_weekly_digest,
)
from app.parsing.discovery import DocumentLoader
from app.services.email_service import EmailSendError
from app.services.analysis import AnalysisResult

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover - fallback for local environments without APScheduler installed
    class BackgroundScheduler:  # type: ignore[override]
        def __init__(self, timezone: str = "UTC") -> None:
            self.jobs: list[dict[str, Any]] = []
            self.running = False

        def add_job(self, func: Callable[..., Any], trigger: str, id: str, replace_existing: bool, **kwargs: Any) -> None:
            self.jobs = [job for job in self.jobs if job["id"] != id]
            self.jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "id": id,
                    "replace_existing": replace_existing,
                    **kwargs,
                }
            )

        def start(self) -> None:
            self.running = True

        def shutdown(self, wait: bool = True) -> None:
            self.running = False


TRANSIENT_TLS_EOF_MARKERS = (
    "unexpected_eof_while_reading",
    "eof occurred in violation of protocol",
)
LIVE_DOCUMENT_FETCH_ATTEMPTS = 2


def _build_live_document_loader(client: httpx.Client) -> DocumentLoader:
    def load(url: str) -> str | None:
        for attempt in range(1, LIVE_DOCUMENT_FETCH_ATTEMPTS + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                if attempt == LIVE_DOCUMENT_FETCH_ATTEMPTS or not _is_retryable_tls_connect_error(exc):
                    return None
                continue
            return response.text
        return None

    return load


def _is_retryable_tls_connect_error(exc: httpx.HTTPError) -> bool:
    if not isinstance(exc, httpx.ConnectError):
        return False
    error_text = str(exc).lower()
    return any(marker in error_text for marker in TRANSIENT_TLS_EOF_MARKERS)


def _load_responses(settings: Settings, responses: dict[str, str] | None) -> dict[str, str]:
    if responses is not None:
        return responses
    if not settings.ingestion_responses_json:
        return {}
    payload = json.loads(settings.ingestion_responses_json)
    return {str(key): str(value) for key, value in payload.items()}


def _stub_analysis_result(settings: Settings) -> AnalysisResult | None:
    if not settings.analysis_stub_response_json:
        return None
    payload = json.loads(settings.analysis_stub_response_json)
    return AnalysisResult(
        summary_ru=payload["summary_ru"],
        topics=list(payload["topics"]),
        format=payload["format"],
        technical_depth=payload["technical_depth"],
        verdict=payload["verdict"],
        verdict_reason=payload["verdict_reason"],
    )


def _analyze_pending_posts(
    session_factory: sessionmaker[Session],
    analysis_client: object,
) -> None:
    """Process posts that have no PostAnalysis row yet."""
    from sqlalchemy import select as _select
    from app.models.post import Post as _Post
    from app.models.post_analysis import PostAnalysis as _PostAnalysis
    from app.services.analysis import AnalysisRequest as _AnalysisRequest
    from app.core.db import session_scope as _session_scope

    with _session_scope(session_factory) as session:
        pending_posts = session.scalars(
            _select(_Post)
            .outerjoin(_PostAnalysis, _PostAnalysis.post_id == _Post.id)
            .where(_PostAnalysis.id.is_(None))
            .order_by(_Post.id)
            .limit(20)
        ).all()

    for post in pending_posts:
        try:
            analysis_client.analyze_and_persist(
                _AnalysisRequest(post_id=post.id, title=post.title, content=post.raw_content)
            )
        except Exception:
            logger.warning("analyze_pending_posts: failed to analyze post %d", post.id)


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    responses: dict[str, str] | None = None,
    document_loader: DocumentLoader | None = None,
    analysis_client_factory: Callable[[], object] | None = None,
    email_transport_factory: Callable[[Session], object | None] | None = None,
    now_provider: Callable[[], datetime] | None = None,
    settings: Settings | None = None,
    enable_scheduler: bool = True,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_now_provider = now_provider or (lambda: datetime.now(UTC))

    app = FastAPI(title="Good News")
    app.state.session_factory = session_factory
    app.state.now_provider = resolved_now_provider
    app.state.settings = resolved_settings
    app.state.responses = _load_responses(resolved_settings, responses)
    app.state.document_client = None
    app.state.document_loader = document_loader
    app.state.analysis_client_factory = analysis_client_factory or (
        lambda: OllamaClient(settings=resolved_settings, session_factory=app.state.session_factory)
    )
    app.state.analysis_stub_result = _stub_analysis_result(resolved_settings)
    app.state.email_transport_factory = email_transport_factory
    app.state.enable_scheduler = enable_scheduler
    app.state.scheduler = None

    instrument_app(app=app, service_name="good-news")

    app.include_router(feedback_router, prefix="/api")
    app.include_router(digests_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(monitoring_router, prefix="/api")
    app.include_router(preferences_router, prefix="/api")
    app.include_router(posts_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(sources_router, prefix="/api")
    app.include_router(want_to_read_router, prefix="/api")

    @app.on_event("startup")
    def ensure_runtime() -> None:
        if app.state.session_factory is None:
            engine = create_engine_from_settings(settings=resolved_settings)
            app.state.session_factory = create_session_factory(engine)
        if app.state.document_loader is None:
            app.state.document_client = httpx.Client(
                follow_redirects=True,
                headers={"User-Agent": "good-news-source-ingestion/1.0"},
                timeout=30.0,
            )
            app.state.document_loader = _build_live_document_loader(app.state.document_client)
        assert_database_schema_is_current(app.state.session_factory)

        if app.state.enable_scheduler:
            scheduler = BackgroundScheduler(timezone="UTC")

            from app.services.source_sync import sync_active_sources

            scheduler.add_job(
                lambda: sync_active_sources(
                    session_factory=app.state.session_factory,
                    responses=app.state.responses,
                    document_loader=app.state.document_loader,
                    now=app.state.now_provider(),
                    failure_threshold=resolved_settings.source_failure_threshold,
                    analysis_service_client=app.state.analysis_client_factory(),
                ),
                trigger="interval",
                id="source-sync",
                minutes=resolved_settings.source_sync_interval_minutes,
                replace_existing=True,
            )

            scheduler.add_job(
                lambda: _analyze_pending_posts(
                    session_factory=app.state.session_factory,
                    analysis_client=app.state.analysis_client_factory(),
                ),
                trigger="interval",
                id="analyze-pending",
                minutes=10,
                replace_existing=True,
            )

            register_daily_digest_job(
                scheduler=scheduler,
                session_factory=app.state.session_factory,
                now_provider=app.state.now_provider,
                runtime_settings=resolved_settings,
            )
            register_weekly_digest_job(
                scheduler=scheduler,
                session_factory=app.state.session_factory,
                now_provider=app.state.now_provider,
                runtime_settings=resolved_settings,
            )
            register_daily_observability_report_job(
                scheduler=scheduler,
                session_factory=app.state.session_factory,
                now_provider=app.state.now_provider,
                runtime_settings=resolved_settings,
            )

            try:
                catch_up_daily_digest_if_needed(
                    session_factory=app.state.session_factory,
                    now=app.state.now_provider(),
                    run_digest=lambda scheduled_for: run_daily_digest(
                        session_factory=app.state.session_factory,
                        now=scheduled_for,
                        runtime_settings=resolved_settings,
                    ),
                )
            except EmailSendError as exc:
                logger.warning("Startup daily digest catch-up failed (will retry on next schedule): %s", exc)
            try:
                catch_up_daily_observability_report_if_needed(
                    session_factory=app.state.session_factory,
                    now=app.state.now_provider(),
                    runtime_settings=resolved_settings,
                    run_report=lambda scheduled_for: run_daily_observability_report(
                        session_factory=app.state.session_factory,
                        now=scheduled_for,
                        runtime_settings=resolved_settings,
                    ),
                )
            except EmailSendError as exc:
                logger.warning("Startup observability report catch-up failed (will retry on next schedule): %s", exc)
            try:
                catch_up_weekly_digest_if_needed(
                    session_factory=app.state.session_factory,
                    now=app.state.now_provider(),
                    run_digest=lambda scheduled_for: run_weekly_digest(
                        session_factory=app.state.session_factory,
                        now=scheduled_for,
                        runtime_settings=resolved_settings,
                    ),
                )
            except EmailSendError as exc:
                logger.warning("Startup weekly digest catch-up failed (will retry on next schedule): %s", exc)

            scheduler.start()
            app.state.scheduler = scheduler

    @app.on_event("shutdown")
    def shutdown_runtime() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            app.state.scheduler = None
        document_client = getattr(app.state, "document_client", None)
        if document_client is not None:
            document_client.close()
            app.state.document_client = None

    return app


app = create_app()
