from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.digest import Digest
from app.models.digest_item import DigestItem
from app.models.feedback import Feedback
from app.models.post import Post
from app.schemas.digest import (
    DigestDetailResponse,
    DigestIncludedPostResponse,
    DigestListItemResponse,
    serialize_digest_datetime,
)

PRODUCT_DIGEST_TYPES = ("daily", "weekly")


def list_sent_digests(session: Session) -> list[DigestListItemResponse]:
    rows = session.execute(
        select(
            Digest.id,
            Digest.digest_type,
            Digest.status,
            Digest.sent_at,
            func.count(DigestItem.id).label("included_post_count"),
        )
        .outerjoin(DigestItem, DigestItem.digest_id == Digest.id)
        .where(
            Digest.digest_type.in_(PRODUCT_DIGEST_TYPES),
            Digest.status == "sent",
            Digest.sent_at.is_not(None),
        )
        .group_by(Digest.id)
        .order_by(Digest.sent_at.desc(), Digest.id.desc())
    ).all()
    return [DigestListItemResponse.from_row(row) for row in rows]


def get_sent_digest_detail(session: Session, digest_id: int) -> DigestDetailResponse | None:
    digest = session.scalar(
        select(Digest).where(
            Digest.id == digest_id,
            Digest.digest_type.in_(PRODUCT_DIGEST_TYPES),
            Digest.status == "sent",
            Digest.sent_at.is_not(None),
        )
    )
    if digest is None:
        return None

    included_posts = session.execute(
        select(Post.id, Post.title, Feedback.state.label("feedback_state"))
        .join(DigestItem, DigestItem.post_id == Post.id)
        .outerjoin(Feedback, Feedback.post_id == Post.id)
        .where(DigestItem.digest_id == digest.id)
        .order_by(DigestItem.rank_position.asc(), DigestItem.id.asc())
    ).all()

    return DigestDetailResponse(
        id=digest.id,
        digest_type=digest.digest_type,
        status=digest.status,
        sent_at=serialize_digest_datetime(digest.sent_at),
        title=digest.subject,
        included_posts=[
            DigestIncludedPostResponse(
                post_id=row.id,
                title=row.title,
                feedback_state=row.feedback_state,
            )
            for row in included_posts
        ],
        rendered_html=digest.html_body,
    )
