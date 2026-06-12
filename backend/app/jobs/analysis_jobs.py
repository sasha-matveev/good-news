from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.services.analysis import AnalysisRequest

logger = logging.getLogger(__name__)

PENDING_BATCH_SIZE = 20


def analyze_pending_posts(
    session_factory: sessionmaker[Session],
    analysis_client: object,
) -> None:
    """Process posts that have no PostAnalysis row yet."""
    with session_scope(session_factory) as session:
        pending_posts = session.scalars(
            select(Post)
            .outerjoin(PostAnalysis, PostAnalysis.post_id == Post.id)
            .where(PostAnalysis.id.is_(None))
            .order_by(Post.id)
            .limit(PENDING_BATCH_SIZE)
        ).all()

    for post in pending_posts:
        try:
            analysis_client.analyze_and_persist(
                AnalysisRequest(post_id=post.id, title=post.title, content=post.raw_content)
            )
        except Exception:
            logger.warning("analyze_pending_posts: failed to analyze post %d", post.id)
