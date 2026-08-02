from __future__ import annotations

import json
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.core.backend_identity import install_backend_identity
from app.core.schema_guard import assert_database_schema_is_current
from app.schemas.source import SourceResponse
from app.parsing.discovery import DocumentLoader
from app.services.analysis_service_client import AnalysisServiceClient
from app.services.ingestion_boundary import (
    DuplicateSourceError,
    SourceOnboardingCommand,
    accept_source_onboarding_command,
)
from app.services.source_sync import sync_active_sources

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


class SyncRunResponse(BaseModel):
    processed_source_ids: list[int]


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


def _create_ingestion_scheduler(
    *,
    session_factory: sessionmaker[Session],
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
    settings: Settings,
    now_provider: Callable[[], datetime],
    analysis_service_client_factory: Callable[[], object],
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: sync_active_sources(
            session_factory=session_factory,
            responses=responses,
            document_loader=document_loader,
            now=now_provider(),
            failure_threshold=settings.source_failure_threshold,
            analysis_service_client=analysis_service_client_factory(),
        ),
        trigger="interval",
        id="source-sync",
        minutes=settings.source_sync_interval_minutes,
        replace_existing=True,
    )
    return scheduler


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    responses: dict[str, str] | None = None,
    document_loader: DocumentLoader | None = None,
    analysis_service_client_factory: Callable[[], object] | None = None,
    settings: Settings | None = None,
    enable_scheduler: bool = True,
    now_provider: Callable[[], datetime] | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_now_provider = now_provider or (lambda: datetime.now(UTC))
    app = FastAPI(title="Good News Source Ingestion Service")
    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.responses = _load_responses(resolved_settings, responses)
    app.state.document_client = None
    app.state.document_loader = document_loader
    app.state.analysis_service_client_factory = analysis_service_client_factory or (
        lambda: AnalysisServiceClient(settings=resolved_settings)
    )
    app.state.enable_scheduler = enable_scheduler
    app.state.now_provider = resolved_now_provider
    app.state.scheduler = None
    install_backend_identity(app)

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
            app.state.scheduler = _create_ingestion_scheduler(
                session_factory=app.state.session_factory,
                responses=app.state.responses,
                document_loader=app.state.document_loader,
                settings=resolved_settings,
                now_provider=app.state.now_provider,
                analysis_service_client_factory=app.state.analysis_service_client_factory,
            )
            app.state.scheduler.start()

    @app.on_event("shutdown")
    def shutdown_scheduler() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            app.state.scheduler = None
        document_client = getattr(app.state, "document_client", None)
        if document_client is not None:
            document_client.close()
            app.state.document_client = None

    def get_session_factory(request: Request) -> sessionmaker[Session]:
        return request.app.state.session_factory

    def get_session(
        session_factory: sessionmaker[Session] = Depends(get_session_factory),
    ) -> Generator[Session, None, None]:
        with session_scope(session_factory) as session:
            yield session

    @app.get("/health")
    def health(session: Session = Depends(get_session)) -> dict[str, str]:
        session.execute(select(1))
        return {"status": "ok"}

    @app.post("/internal/ingestion/onboarding-commands", response_model=SourceResponse)
    def onboarding_command(
        payload: SourceOnboardingCommand,
        request: Request,
        session: Session = Depends(get_session),
    ) -> SourceResponse:
        try:
            source = accept_source_onboarding_command(
                session=session,
                command=payload,
                responses=request.app.state.responses,
                document_loader=request.app.state.document_loader,
            )
        except DuplicateSourceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return SourceResponse.from_model(source)

    @app.post("/internal/ingestion/sync/run-once", response_model=SyncRunResponse)
    def run_sync_once(request: Request) -> SyncRunResponse:
        processed_source_ids = sync_active_sources(
            session_factory=request.app.state.session_factory,
            responses=request.app.state.responses,
            document_loader=request.app.state.document_loader,
            now=request.app.state.now_provider(),
            failure_threshold=request.app.state.settings.source_failure_threshold,
            analysis_service_client=request.app.state.analysis_service_client_factory(),
        )
        return SyncRunResponse(processed_source_ids=processed_source_ids)

    return app


app = create_app()
