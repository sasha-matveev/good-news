from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.content_api_service.main import create_app
from app.models.base import Base
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.read_later import ReadLater
from app.models.source import Source
from app.testing.schema import stamp_schema_head


def build_client() -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    app = create_app(
        session_factory=session_factory,
        discovery_responses={},
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
    )
    return TestClient(app), session_factory


def test_get_posts_defaults_to_last_month_and_returns_placeholder_ranking_order() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(Source(id=2, display_name="Beta", original_url="https://beta.example", status="ready"))
        session.add_all(
            [
                Post(
                    source_id=1,
                    canonical_url="https://alpha.example/posts/older",
                    title="Older",
                    published_at=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
                    raw_content="Too old for the default window.",
                    content_hash="older-hash",
                    ingest_metadata='{"strategy":"feed"}',
                ),
                Post(
                    source_id=2,
                    canonical_url="https://beta.example/posts/newer",
                    title="Newer",
                    published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                    raw_content="Fresh enough for the default window.",
                    content_hash="newer-hash",
                    ingest_metadata='{"strategy":"feed"}',
                ),
            ]
        )

    response = client.get("/api/posts")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 2,
            "source_id": 2,
            "source_name": "Beta",
            "canonical_url": "https://beta.example/posts/newer",
            "title": "Newer",
            "published_at": "2026-04-20T09:00:00Z",
            "raw_content": "Fresh enough for the default window.",
            "feedback_state": None,
            "read_later": False,
            "summary_ru": None,
            "verdict": None,
            "verdict_reason": None,
            "ranking_explanation": "feedback=none; source_affinity=0.0; topic_affinity=0.0; format_affinity=0.0; practical=0.1; depth=0.0; recency=0.3",
        }
    ]


def test_get_posts_supports_window_all_source_filter_and_feedback_filter() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add_all(
            [
                Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"),
                Source(id=2, display_name="Beta", original_url="https://beta.example", status="ready"),
            ]
        )
        session.add_all(
            [
                Post(
                    id=1,
                    source_id=1,
                    canonical_url="https://alpha.example/posts/one",
                    title="Alpha One",
                    published_at=datetime(2026, 2, 10, 8, 0, tzinfo=UTC),
                    raw_content="Saved as interesting.",
                    content_hash="alpha-one",
                    ingest_metadata='{"strategy":"feed"}',
                ),
                Post(
                    id=2,
                    source_id=1,
                    canonical_url="https://alpha.example/posts/two",
                    title="Alpha Two",
                    published_at=datetime(2026, 2, 11, 8, 0, tzinfo=UTC),
                    raw_content="No feedback yet.",
                    content_hash="alpha-two",
                    ingest_metadata='{"strategy":"feed"}',
                ),
                Post(
                    id=3,
                    source_id=2,
                    canonical_url="https://beta.example/posts/one",
                    title="Beta One",
                    published_at=datetime(2026, 2, 12, 8, 0, tzinfo=UTC),
                    raw_content="Interesting but from another source.",
                    content_hash="beta-one",
                    ingest_metadata='{"strategy":"feed"}',
                ),
            ]
        )
        session.add_all(
            [
                Feedback(post_id=1, state="interesting"),
                Feedback(post_id=3, state="interesting"),
            ]
        )

    response = client.get("/api/posts?window=all&source_id=1&feedback_state=interesting")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "source_id": 1,
            "source_name": "Alpha",
            "canonical_url": "https://alpha.example/posts/one",
            "title": "Alpha One",
            "published_at": "2026-02-10T08:00:00Z",
            "raw_content": "Saved as interesting.",
            "feedback_state": "interesting",
            "read_later": False,
            "summary_ru": None,
            "verdict": None,
            "verdict_reason": None,
            "ranking_explanation": "feedback=interesting; source_affinity=0.4; topic_affinity=0.0; format_affinity=0.0; practical=0.1; depth=0.0; recency=0.3",
        }
    ]


def test_get_posts_supports_want_to_read_filter_and_no_dedicated_read_endpoint() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add_all(
            [
                Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"),
                Source(id=2, display_name="Beta", original_url="https://beta.example", status="ready"),
            ]
        )
        session.add_all(
            [
                Post(
                    id=1,
                    source_id=1,
                    canonical_url="https://alpha.example/posts/one",
                    title="Alpha One",
                    published_at=datetime(2026, 2, 10, 8, 0, tzinfo=UTC),
                    raw_content="Saved earlier.",
                    content_hash="alpha-one",
                    ingest_metadata='{"strategy":"feed"}',
                ),
                Post(
                    id=2,
                    source_id=2,
                    canonical_url="https://beta.example/posts/two",
                    title="Beta Two",
                    published_at=datetime(2026, 2, 11, 8, 0, tzinfo=UTC),
                    raw_content="Saved later.",
                    content_hash="beta-two",
                    ingest_metadata='{"strategy":"feed"}',
                ),
                Post(
                    id=3,
                    source_id=2,
                    canonical_url="https://beta.example/posts/three",
                    title="Beta Three",
                    published_at=datetime(2026, 2, 12, 8, 0, tzinfo=UTC),
                    raw_content="Not saved.",
                    content_hash="beta-three",
                    ingest_metadata='{"strategy":"feed"}',
                ),
            ]
        )
        session.add_all(
            [
                Feedback(post_id=1, state="want_to_read"),
                Feedback(post_id=2, state="want_to_read"),
                Feedback(post_id=3, state="interesting"),
            ]
        )

    filtered_response = client.get("/api/posts?window=all&feedback_state=want_to_read")

    assert filtered_response.status_code == 200
    assert [item["id"] for item in filtered_response.json()] == [2, 1]
    assert [item["feedback_state"] for item in filtered_response.json()] == ["want_to_read", "want_to_read"]

    removed_endpoint_response = client.get("/api/want-to-read")

    assert removed_endpoint_response.status_code == 404


def test_get_posts_sort_match_ranks_by_match_score() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add_all([
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Older but interesting",
                published_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
                raw_content="Older content.",
                content_hash="hash-1",
                ingest_metadata='{"strategy":"feed"}',
            ),
            Post(
                id=2,
                source_id=1,
                canonical_url="https://alpha.example/posts/two",
                title="Newer but no feedback",
                published_at=datetime(2026, 4, 25, 8, 0, tzinfo=UTC),
                raw_content="Newer content.",
                content_hash="hash-2",
                ingest_metadata='{"strategy":"feed"}',
            ),
        ])
        session.add(Feedback(post_id=1, state="interesting"))

    response = client.get("/api/posts?sort=match&window=all")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids[0] == 1, f"sort=match should rank the interesting post first; got order {ids}"


def test_get_posts_sort_date_returns_newest_first() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add_all([
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Older but interesting",
                published_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
                raw_content="Older content.",
                content_hash="hash-1",
                ingest_metadata='{"strategy":"feed"}',
            ),
            Post(
                id=2,
                source_id=1,
                canonical_url="https://alpha.example/posts/two",
                title="Newer no feedback",
                published_at=datetime(2026, 4, 25, 8, 0, tzinfo=UTC),
                raw_content="Newer content.",
                content_hash="hash-2",
                ingest_metadata='{"strategy":"feed"}',
            ),
        ])
        session.add(Feedback(post_id=1, state="interesting"))

    response = client.get("/api/posts?sort=date&window=all")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids[0] == 2, f"sort=date should put the newest post first; got order {ids}"


# ---------------------------------------------------------------------------
# T006: read_later field in PostResponse
# ---------------------------------------------------------------------------


def test_get_posts_includes_read_later_field_defaulting_to_false() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh content.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    response = client.get("/api/posts?window=all")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["read_later"] is False


def test_get_posts_reflects_read_later_true_when_row_exists() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh content.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(ReadLater(post_id=1))

    response = client.get("/api/posts?window=all")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["read_later"] is True


# ---------------------------------------------------------------------------
# T006: POST /api/posts/{id}/read-later
# ---------------------------------------------------------------------------


def test_post_read_later_saves_and_returns_read_later_true() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh content.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    response = client.post("/api/posts/1/read-later", json={"saved": True})

    assert response.status_code == 200
    assert response.json() == {"post_id": 1, "read_later": True}

    with session_scope(session_factory) as session:
        row = session.query(ReadLater).filter(ReadLater.post_id == 1).one()
    assert row is not None


def test_post_read_later_clears_and_returns_read_later_false() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh content.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(ReadLater(post_id=1))

    response = client.post("/api/posts/1/read-later", json={"saved": False})

    assert response.status_code == 200
    assert response.json() == {"post_id": 1, "read_later": False}

    with session_scope(session_factory) as session:
        row = session.query(ReadLater).filter(ReadLater.post_id == 1).one_or_none()
    assert row is None


def test_post_read_later_is_independent_from_feedback_state() -> None:
    """Saving as read_later must NOT change feedback_state and vice versa."""
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh content.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))

    client.post("/api/posts/1/read-later", json={"saved": True})

    with session_scope(session_factory) as session:
        feedback = session.query(Feedback).filter(Feedback.post_id == 1).one()
        rl = session.query(ReadLater).filter(ReadLater.post_id == 1).one()

    assert feedback.state == "interesting"
    assert rl is not None


def test_post_read_later_returns_404_for_missing_post() -> None:
    client, _ = build_client()

    response = client.post("/api/posts/999/read-later", json={"saved": True})

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# T006: POST /api/posts/{id}/open (article-click tracking)
# ---------------------------------------------------------------------------


def test_post_open_returns_opened_true() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh content.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    response = client.post("/api/posts/1/open")

    assert response.status_code == 200
    assert response.json() == {"opened": True}


def test_post_open_returns_404_for_missing_post() -> None:
    client, _ = build_client()

    response = client.post("/api/posts/999/open")

    assert response.status_code == 404


def test_posts_api_normalizes_empty_verdict_to_null() -> None:
    """GOO-49: PostResponse.from_row must return None (not '') for empty verdict/verdict_reason."""
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Post with empty verdict",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Some content.",
                content_hash="empty-verdict-hash",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(
            PostAnalysis(
                post_id=1,
                summary_ru="Some summary.",
                metadata_json=json.dumps(
                    {
                        "topics": ["devops"],
                        "format": "guide",
                        "technical_depth": "medium",
                        "verdict": "",
                        "verdict_reason": "",
                    },
                    sort_keys=True,
                ),
            )
        )

    response = client.get("/api/posts?sort=match&window=all")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["verdict"] is None, f"Expected verdict=null, got {data[0]['verdict']!r}"
    assert data[0]["verdict_reason"] is None, f"Expected verdict_reason=null, got {data[0]['verdict_reason']!r}"


def test_get_posts_supports_limit_and_offset_pagination() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add_all([
            Post(
                id=i,
                source_id=1,
                canonical_url=f"https://alpha.example/posts/{i}",
                title=f"Post {i}",
                published_at=datetime(2026, 4, i, 9, 0, tzinfo=UTC),
                raw_content="Content.",
                content_hash=f"hash-{i}",
                ingest_metadata='{"strategy":"feed"}',
            )
            for i in range(1, 6)
        ])

    first_page = client.get("/api/posts?window=all&sort=date&limit=2").json()
    second_page = client.get("/api/posts?window=all&sort=date&limit=2&offset=2").json()

    assert len(first_page) == 2
    assert len(second_page) == 2
    assert first_page[0]["id"] != second_page[0]["id"], "Pages must not overlap"

    all_ids = {p["id"] for p in first_page + second_page}
    assert len(all_ids) == 4, "All returned posts must be distinct"
