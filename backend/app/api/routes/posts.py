from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.models.feedback import Feedback
from app.models.post import Post
from app.schemas.post import PostResponse
from app.services.post_listing import list_posts as list_post_responses
from app.services.read_later_service import toggle_read_later

router = APIRouter(tags=["posts"])


class ReadLaterRequest(BaseModel):
    saved: bool


class ReadLaterResponse(BaseModel):
    post_id: int
    read_later: bool


class OpenResponse(BaseModel):
    opened: bool


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_now(request: Request) -> datetime:
    return request.app.state.now_provider()


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


@router.get("/posts", response_model=list[PostResponse])
def list_posts(
    source_id: int | None = None,
    feedback_state: str | None = None,
    window: str = Query(default="last_month"),
    sort: Literal["match", "date"] = Query(default="match"),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    read_later: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> list[PostResponse]:
    return list_post_responses(
        session,
        source_id=source_id,
        feedback_state=feedback_state,
        now=now,
        window=window,
        sort=sort,
        limit=limit,
        offset=offset,
        read_later=read_later,
    )


@router.post("/posts/{post_id}/read-later", response_model=ReadLaterResponse)
def update_read_later(
    post_id: int,
    payload: ReadLaterRequest,
    session: Session = Depends(get_session),
) -> ReadLaterResponse:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    read_later = toggle_read_later(session, post_id=post_id, saved=payload.saved)
    session.commit()
    return ReadLaterResponse(post_id=post_id, read_later=read_later)


@router.post("/posts/{post_id}/open", response_model=OpenResponse)
def track_post_open(
    post_id: int,
    session: Session = Depends(get_session),
) -> OpenResponse:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return OpenResponse(opened=True)
