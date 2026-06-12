from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.ai.gemini_client import GeminiClient
from app.api.routes.digests import router as digests_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.health import router as health_router
from app.api.routes.internal_jobs import router as internal_jobs_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.preferences import router as preferences_router
from app.api.routes.posts import router as posts_router
from app.api.routes.settings import router as settings_router
from app.api.routes.sources import router as sources_router
from app.api.routes.want_to_read import router as want_to_read_router
from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory
from app.core.observability import instrument_app
from app.core.request_auth import install_user_auth_middleware
from app.core.schema_guard import assert_database_schema_is_current
from app.parsing.discovery import DocumentLoader
from app.services.analysis import AnalysisResult

logger = logging.getLogger(__name__)

TRANSIENT_TLS_EOF_MARKERS = (
    "unexpected_eof_while_reading",
    "eof occurred in violation of protocol",
)
LIVE_DOCUMENT_FETCH_ATTEMPTS = 2

LOCAL_DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


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


def _cors_origins(settings: Settings) -> list[str]:
    origins = list(LOCAL_DEV_ORIGINS)
    frontend_origin = (settings.public_frontend_origin or "").strip().rstrip("/")
    if frontend_origin:
        origins.append(frontend_origin)
    return origins


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    responses: dict[str, str] | None = None,
    document_loader: DocumentLoader | None = None,
    analysis_client_factory: Callable[[], object] | None = None,
    email_transport_factory: Callable[[Session], object | None] | None = None,
    now_provider: Callable[[], datetime] | None = None,
    settings: Settings | None = None,
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
        lambda: GeminiClient(settings=resolved_settings, session_factory=app.state.session_factory)
    )
    app.state.analysis_stub_result = _stub_analysis_result(resolved_settings)
    app.state.email_transport_factory = email_transport_factory

    instrument_app(app=app, service_name="good-news")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(resolved_settings),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_user_auth_middleware(app, resolved_settings)

    app.include_router(feedback_router, prefix="/api")
    app.include_router(digests_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(monitoring_router, prefix="/api")
    app.include_router(preferences_router, prefix="/api")
    app.include_router(posts_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(sources_router, prefix="/api")
    app.include_router(want_to_read_router, prefix="/api")
    app.include_router(internal_jobs_router)

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

    @app.on_event("shutdown")
    def shutdown_runtime() -> None:
        document_client = getattr(app.state, "document_client", None)
        if document_client is not None:
            document_client.close()
            app.state.document_client = None

    return app


app = create_app()
