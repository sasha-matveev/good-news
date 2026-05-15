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
from app.services.ingestion_boundary import SourceOnboardingCommand
from app.services.source_ingestion_service_client import DuplicateSourceError, SourceIngestionServiceClient

router = APIRouter(tags=["sources"])


class SourceSyncResponse(BaseModel):
    processed_source_ids: list[int]


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_source_ingestion_client(request: Request) -> SourceIngestionServiceClient:
    factory = getattr(request.app.state, "source_ingestion_client_factory", None)
    if factory is None:
        settings = request.app.state.settings
        return SourceIngestionServiceClient(settings=settings)
    return factory()


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreateRequest,
    source_ingestion_client: SourceIngestionServiceClient = Depends(get_source_ingestion_client),
) -> SourceResponse:
    try:
        return source_ingestion_client.onboard_source(
            SourceOnboardingCommand(url=payload.url),
        )
    except DuplicateSourceError as exc:
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
    source_ingestion_client: SourceIngestionServiceClient = Depends(get_source_ingestion_client),
) -> SourceSyncResponse:
    try:
        processed_source_ids = source_ingestion_client.run_sync_once()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Source ingestion service is unavailable.",
        ) from exc

    return SourceSyncResponse(processed_source_ids=processed_source_ids)
