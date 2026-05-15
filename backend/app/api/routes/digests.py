from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.schemas.digest import DigestDetailResponse, DigestListItemResponse
from app.services.digest_history import get_sent_digest_detail, list_sent_digests

router = APIRouter(tags=["digests"])


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


@router.get("/digests", response_model=list[DigestListItemResponse])
def list_digests(session: Session = Depends(get_session)) -> list[DigestListItemResponse]:
    return list_sent_digests(session)


@router.get("/digests/{digest_id}", response_model=DigestDetailResponse)
def get_digest_detail(digest_id: int, session: Session = Depends(get_session)) -> DigestDetailResponse:
    digest = get_sent_digest_detail(session, digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest
