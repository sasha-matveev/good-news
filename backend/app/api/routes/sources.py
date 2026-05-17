from __future__ import annotations

import logging
import threading
import time
from collections.abc import Generator
from typing import Any, Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from sqlalchemy import delete as sa_delete

from app.core.db import session_scope
from app.models.digest_item import DigestItem
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.read_later import ReadLater
from app.models.setting import TechnicalEvent
from app.models.source import Source
from app.parsing.discovery import normalize_source_url
from app.schemas.source import SourceCreateRequest, SourceResponse, SourceUpdateRequest
from app.services.ingestion_boundary import (
    DuplicateSourceError,
    SourceOnboardingCommand,
)
from app.services.source_ingestion_service_client import (
    DuplicateSourceError as ServiceDuplicateSourceError,
    SourceIngestionServiceClient,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sources"])


class SourceSyncResponse(BaseModel):
    processed_source_ids: list[int]


class SourceLogResponse(BaseModel):
    log: list[dict[str, Any]]
    done: bool
    status: str | None


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


def _is_monolith(request: Request) -> bool:
    """Return True when running in the merged monolith (direct function calls, no HTTP hop)."""
    return getattr(request.app.state, "document_loader", None) is not None or getattr(
        request.app.state, "analysis_client_factory", None
    ) is not None


def _get_source_logs(app_state: Any) -> dict[int, list[dict[str, Any]]]:
    if not hasattr(app_state, "source_logs"):
        app_state.source_logs = {}
    return app_state.source_logs  # type: ignore[no-any-return]


def _run_onboarding_background(
    source_id: int,
    session_factory: sessionmaker[Session],
    responses: dict[str, str],
    document_loader: Any,
    source_logs: dict[int, list[dict[str, Any]]],
    sync_after_ready: Callable[[Callable[[str], None]], None] | None = None,
) -> None:
    """Run source discovery in a background thread with a fresh DB session."""
    log_lines = source_logs.setdefault(source_id, [])

    def log(msg: str) -> None:
        log_lines.append({"ts": time.time(), "msg": msg})

    # The main request session commits only after the endpoint handler returns.
    # Retry until the record is visible in a new session (usually < 300 ms).
    _MAX_WAIT_SECONDS = 5
    _RETRY_INTERVAL = 0.2
    source = None
    for _ in range(int(_MAX_WAIT_SECONDS / _RETRY_INTERVAL)):
        with session_scope(session_factory) as probe:
            source = probe.get(Source, source_id)
        if source is not None:
            break
        time.sleep(_RETRY_INTERVAL)

    if source is None:
        log("Error: source record not found in DB after waiting")
        return

    final_status = "failed"
    try:
        from app.services.source_onboarding import onboard_source
        with session_scope(session_factory) as session:
            source = session.get(Source, source_id)
            if source is None:
                log("Error: source disappeared from DB")
                return
            try:
                onboard_source(
                    source,
                    session=session,
                    responses=responses,
                    document_loader=document_loader,
                    log_cb=log,
                )
                final_status = source.status
            except Exception as exc:
                logger.exception("Onboarding background task failed for source %d", source_id)
                log(f"Error: {exc}")
                source.status = "failed"
                source.needs_readaptation = True
                source.readaptation_reason = str(exc)
    except Exception as exc:
        logger.exception("Fatal error in onboarding background task for source %d", source_id)
        log(f"Fatal error: {exc}")
        return

    # Auto-sync immediately after a successful discovery so the source gets posts right away.
    if final_status == "ready" and sync_after_ready is not None:
        log("─" * 40)
        log("Discovery complete — running initial sync...")
        try:
            sync_after_ready(log)
        except Exception as exc:
            logger.exception("Auto-sync after onboarding failed for source %d", source_id)
            log(f"Sync error: {exc}")


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreateRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> SourceResponse:
    # Monolith path: create the record immediately and run discovery in background.
    if _is_monolith(request):
        normalized_url = normalize_source_url(payload.url)

        existing = session.scalar(select(Source).where(Source.original_url == normalized_url))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Source already exists for {normalized_url}")

        source = Source(original_url=normalized_url, status="discovering")
        session.add(source)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Source already exists for {normalized_url}") from exc

        source_logs = _get_source_logs(request.app.state)
        source_logs[source.id] = [{"ts": time.time(), "msg": f"Source record created (id={source.id})"}]

        # Snapshot everything the background thread needs before the request session closes.
        source_id = source.id
        _session_factory = request.app.state.session_factory
        _responses = getattr(request.app.state, "responses", {})
        _document_loader = getattr(request.app.state, "document_loader", None)
        _app_state = request.app.state

        def _sync_after_ready(log_cb: Callable[[str], None]) -> None:
            from app.services.source_sync import sync_active_sources
            processed = sync_active_sources(
                session_factory=_app_state.session_factory,
                responses=getattr(_app_state, "responses", {}),
                document_loader=getattr(_app_state, "document_loader", None),
                now=_app_state.now_provider(),
                failure_threshold=_app_state.settings.source_failure_threshold,
                analysis_service_client=_app_state.analysis_client_factory(),
            )
            count = len(processed)
            log_cb(f"Sync complete — {count} source{'s' if count != 1 else ''} processed")

        thread = threading.Thread(
            target=_run_onboarding_background,
            args=(source_id, _session_factory, _responses, _document_loader, source_logs),
            kwargs={"sync_after_ready": _sync_after_ready},
            daemon=True,
            name=f"onboarding-{source_id}",
        )
        thread.start()

        return SourceResponse.from_model(source)

    # Legacy microservice path: delegate via HTTP client.
    factory = getattr(request.app.state, "source_ingestion_client_factory", None)
    if factory is None:
        settings = request.app.state.settings
        client: SourceIngestionServiceClient = SourceIngestionServiceClient(settings=settings)
    else:
        client = factory()
    try:
        return client.onboard_source(SourceOnboardingCommand(url=payload.url))
    except (DuplicateSourceError, ServiceDuplicateSourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Source ingestion service is unavailable.",
        ) from exc


@router.get("/sources/{source_id}/log", response_model=SourceLogResponse)
def get_source_log(
    source_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> SourceLogResponse:
    source_logs = _get_source_logs(request.app.state)
    log_lines = list(source_logs.get(source_id, []))

    source = session.get(Source, source_id)
    current_status = source.status if source else None
    done = current_status != "discovering"

    return SourceLogResponse(log=log_lines, done=done, status=current_status)


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(session: Session = Depends(get_session)) -> list[SourceResponse]:
    sources = session.scalars(select(Source).order_by(Source.id)).all()
    post_counts: dict[int, int] = dict(
        session.execute(
            select(Post.source_id, func.count(Post.id).label("cnt")).group_by(Post.source_id)
        ).all()
    )
    return [SourceResponse.from_model(s, post_count=post_counts.get(s.id, 0)) for s in sources]


@router.patch("/sources/{source_id}", response_model=SourceResponse)
def update_source(
    source_id: int,
    payload: SourceUpdateRequest,
    session: Session = Depends(get_session),
) -> SourceResponse:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    source.active = payload.active
    session.flush()
    post_count: int = session.scalar(
        select(func.count(Post.id)).where(Post.source_id == source_id)
    ) or 0
    return SourceResponse.from_model(source, post_count=post_count)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: int,
    session: Session = Depends(get_session),
) -> None:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    post_ids_query = select(Post.id).where(Post.source_id == source_id)
    post_ids = list(session.scalars(post_ids_query).all())

    if post_ids:
        session.execute(sa_delete(DigestItem).where(DigestItem.post_id.in_(post_ids)))
        session.execute(sa_delete(PostAnalysis).where(PostAnalysis.post_id.in_(post_ids)))
        session.execute(sa_delete(ReadLater).where(ReadLater.post_id.in_(post_ids)))
        session.execute(sa_delete(Feedback).where(Feedback.post_id.in_(post_ids)))
        session.execute(sa_delete(Post).where(Post.source_id == source_id))

    session.execute(sa_delete(TechnicalEvent).where(TechnicalEvent.source_id == source_id))
    session.delete(source)


@router.post("/sources/{source_id}/sync", response_model=SourceSyncResponse)
def sync_single_source(
    source_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> SourceSyncResponse:
    """Sync a single source by ID regardless of active state."""
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    if _is_monolith(request):
        from app.services.source_sync import sync_active_sources

        processed_source_ids = sync_active_sources(
            session_factory=request.app.state.session_factory,
            responses=getattr(request.app.state, "responses", {}),
            document_loader=getattr(request.app.state, "document_loader", None),
            now=request.app.state.now_provider(),
            failure_threshold=request.app.state.settings.source_failure_threshold,
            analysis_service_client=request.app.state.analysis_client_factory(),
            source_ids=[source_id],
        )
        return SourceSyncResponse(processed_source_ids=processed_source_ids)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Per-source sync is only available in monolith mode.",
    )


class RefreshPostDatesResponse(BaseModel):
    checked: int
    updated: int


@router.post("/sources/{source_id}/refresh-post-dates", response_model=RefreshPostDatesResponse)
def refresh_source_post_dates(
    source_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RefreshPostDatesResponse:
    """Re-fetch article pages for posts in this source that lack a publication date.

    Targets up to 60 most-recently-ingested posts with published_at IS NULL,
    fetches each article page, and fills in the date when found.
    """
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    document_loader = getattr(request.app.state, "document_loader", None)
    if document_loader is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="refresh-post-dates is only available in monolith mode.",
        )

    from app.services.source_sync import refresh_post_dates

    result = refresh_post_dates(
        session=session,
        source_id=source_id,
        document_loader=document_loader,
    )
    return RefreshPostDatesResponse(checked=result["checked"], updated=result["updated"])


@router.post("/sources/sync", response_model=SourceSyncResponse)
def sync_sources_once(
    request: Request,
    session: Session = Depends(get_session),
) -> SourceSyncResponse:
    # Monolith path: call sync directly.
    if _is_monolith(request):
        from app.services.source_sync import sync_active_sources

        processed_source_ids = sync_active_sources(
            session_factory=request.app.state.session_factory,
            responses=getattr(request.app.state, "responses", {}),
            document_loader=getattr(request.app.state, "document_loader", None),
            now=request.app.state.now_provider(),
            failure_threshold=request.app.state.settings.source_failure_threshold,
            analysis_service_client=request.app.state.analysis_client_factory(),
        )
        return SourceSyncResponse(processed_source_ids=processed_source_ids)

    # Legacy microservice path.
    factory = getattr(request.app.state, "source_ingestion_client_factory", None)
    if factory is None:
        settings = request.app.state.settings
        client: SourceIngestionServiceClient = SourceIngestionServiceClient(settings=settings)
    else:
        client = factory()
    try:
        processed_source_ids = client.run_sync_once()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Source ingestion service is unavailable.",
        ) from exc

    return SourceSyncResponse(processed_source_ids=processed_source_ids)
