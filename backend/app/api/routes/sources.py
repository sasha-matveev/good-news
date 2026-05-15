from __future__ import annotations

from collections.abc import Generator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.models.source import Source
from app.schemas.source import SourceCreateRequest, SourceResponse, SourceUpdateRequest
from app.services.ingestion_boundary import (
    DuplicateSourceError,
    SourceOnboardingCommand,
    accept_source_onboarding_command,
)
from app.services.source_ingestion_service_client import (
    DuplicateSourceError as ServiceDuplicateSourceError,
    SourceIngestionServiceClient,
)

router = APIRouter(tags=["sources"])


class SourceSyncResponse(BaseModel):
    processed_source_ids: list[int]


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


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreateRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> SourceResponse:
    # Monolith path: call ingestion boundary directly.
    if _is_monolith(request):
        try:
            source = accept_source_onboarding_command(
                session=session,
                command=SourceOnboardingCommand(url=payload.url),
                responses=getattr(request.app.state, "responses", {}),
                document_loader=getattr(request.app.state, "document_loader", None),
            )
        except DuplicateSourceError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
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


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(session: Session = Depends(get_session)) -> list[SourceResponse]:
    sources = session.scalars(select(Source).order_by(Source.id)).all()
    return [SourceResponse.from_model(source) for source in sources]


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
    return SourceResponse.from_model(source)


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
