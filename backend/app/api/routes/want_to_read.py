from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.models.feedback import Feedback
from app.models.post import Post
from app.schemas.want_to_read import WantToReadUpdateRequest, WantToReadUpdateResponse

router = APIRouter(tags=["want-to-read"])


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


@router.put("/want-to-read/{post_id}", response_model=WantToReadUpdateResponse)
def update_want_to_read_state(
    post_id: int,
    payload: WantToReadUpdateRequest,
    session: Session = Depends(get_session),
) -> WantToReadUpdateResponse:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    feedback = session.scalar(select(Feedback).where(Feedback.post_id == post_id))

    if payload.saved:
        if feedback is None:
            feedback = Feedback(post_id=post_id, state="want_to_read")
            session.add(feedback)
        else:
            feedback.state = "want_to_read"
    elif feedback is not None and feedback.state == "want_to_read":
        session.delete(feedback)
        feedback = None

    session.commit()
    return WantToReadUpdateResponse(
        post_id=post_id,
        saved=payload.saved,
        feedback_state=None if feedback is None else feedback.state,
    )
