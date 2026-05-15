from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.read_later import ReadLater


def toggle_read_later(session: Session, *, post_id: int, saved: bool) -> bool:
    """Set or clear the read_later flag for a post.

    Returns True when the post is now marked as read-later, False otherwise.
    Does not touch feedback state.
    """
    row = session.scalar(select(ReadLater).where(ReadLater.post_id == post_id))

    if saved and row is None:
        session.add(ReadLater(post_id=post_id))
    elif not saved and row is not None:
        session.delete(row)

    session.flush()
    return saved
