from __future__ import annotations

from collections.abc import Generator
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.db import session_scope
from app.models.feedback import Feedback
from app.models.post import Post
from app.schemas.feedback import FeedbackResponse, FeedbackUpdateRequest

router = APIRouter(tags=["feedback"])

VALID_STATES = {"interesting", "not_interesting", "want_to_read", "norm"}


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


def upsert_feedback_state(session: Session, post_id: int, state: str) -> Feedback:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    feedback = session.scalar(select(Feedback).where(Feedback.post_id == post_id))
    if feedback is None:
        feedback = Feedback(post_id=post_id, state=state)
        session.add(feedback)
    else:
        feedback.state = state

    session.flush()
    return feedback


@router.put("/feedback/{post_id}", response_model=FeedbackResponse)
def update_feedback(
    post_id: int,
    payload: FeedbackUpdateRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    feedback = upsert_feedback_state(session, post_id, payload.state)
    session.commit()
    return FeedbackResponse(post_id=feedback.post_id, state=feedback.state)


@router.get("/feedback/{post_id}/{state}")
def save_feedback(
    post_id: int,
    state: str,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    if state not in VALID_STATES:
        raise HTTPException(status_code=404, detail="Unknown feedback state")

    feedback = upsert_feedback_state(session, post_id, state)
    session.commit()

    settings = getattr(request.app.state, "settings", None) or Settings.from_env()
    digest_id = request.query_params.get("digest_id")
    if digest_id:
        target_path = "/want-to-read" if state == "want_to_read" else "/digests"
        query = urlencode(
            {
                "digest_id": digest_id,
                "feedback": feedback.state,
                "from": "digest_email",
                "post_id": str(feedback.post_id),
            }
        )
        target_url = f"{settings.frontend_public_origin_url()}{target_path}?{query}"
    else:
        target_path = "/want-to-read" if state == "want_to_read" else "/feed"
        target_url = f"{settings.frontend_public_origin_url()}{target_path}"
    return RedirectResponse(
        url=target_url,
        status_code=307,
    )
