from __future__ import annotations

import json
from datetime import UTC, datetime

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.digest import Digest
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source
from app.services.digest_service import generate_daily_digest, generate_weekly_digest


def test_generate_daily_digest_returns_top_five_ranked_posts_and_exact_remainder() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        for index in range(1, 7):
            session.add(
                Post(
                    id=index,
                    source_id=1,
                    canonical_url=f"https://alpha.example/posts/{index}",
                    title=f"Post {index}",
                    published_at=datetime(2026, 4, 26, index, 0, tzinfo=UTC),
                    raw_content=f"Content {index}",
                    content_hash=f"hash-{index}",
                    ingest_metadata='{"strategy":"feed"}',
                )
            )
            session.add(
                PostAnalysis(
                    post_id=index,
                    summary_ru=f"Русское summary {index}",
                    metadata_json=json.dumps(
                        {
                            "topics": ["observability"] if index <= 3 else ["frontend"],
                            "format": "postmortem" if index <= 3 else "news",
                            "technical_depth": "deep" if index <= 3 else "medium",
                            "verdict": "interesting" if index <= 3 else "skip",
                            "verdict_reason": f"Reason {index}",
                        }
                    ),
                )
            )
        session.add(Feedback(post_id=1, state="interesting"))
        session.add(Feedback(post_id=2, state="want_to_read"))
        session.add(Feedback(post_id=6, state="not_interesting"))

    with session_scope(session_factory) as session:
        digest = generate_daily_digest(
            session=session,
            now=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
            frontend_base_url="https://good-news.example",
            content_api_base_url="https://api.good-news.example",
        )

    assert [post.post_id for post in digest.posts] == [2, 1, 3, 4, 5]
    assert digest.more_count == 1
    assert "1 more post in the collection" in digest.html_body
    assert digest.digest_id > 0
    assert (
        f'href="https://api.good-news.example/api/feedback/2/interesting?digest_id={digest.digest_id}"'
        in digest.html_body
    )


def test_generate_weekly_digest_uses_recent_window_and_persists_weekly_type() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        for index, published_at in [
            (1, datetime(2026, 4, 24, 9, 0, tzinfo=UTC)),
            (2, datetime(2026, 4, 21, 9, 0, tzinfo=UTC)),
            (3, datetime(2026, 4, 19, 9, 0, tzinfo=UTC)),
        ]:
            session.add(
                Post(
                    id=index,
                    source_id=1,
                    canonical_url=f"https://alpha.example/posts/{index}",
                    title=f"Post {index}",
                    published_at=published_at,
                    raw_content=f"Content {index}",
                    content_hash=f"hash-{index}",
                    ingest_metadata='{"strategy":"feed"}',
                )
            )
            session.add(
                PostAnalysis(
                    post_id=index,
                    summary_ru=f"Weekly summary {index}",
                    metadata_json=json.dumps(
                        {
                            "topics": ["backend"],
                            "format": "news",
                            "technical_depth": "medium",
                            "verdict": "interesting",
                            "verdict_reason": f"Reason {index}",
                        }
                    ),
                )
            )

    with session_scope(session_factory) as session:
        digest = generate_weekly_digest(
            session=session,
            now=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
            frontend_base_url="https://good-news.example",
            content_api_base_url="https://api.good-news.example",
        )
        stored_digest = session.get(Digest, digest.digest_id)

    assert [post.post_id for post in digest.posts] == [1, 2]
    assert digest.more_count == 0
    assert "weekly digest" in digest.subject.lower()
    assert stored_digest is not None
    assert stored_digest.digest_type == "weekly"
