from __future__ import annotations

from datetime import UTC, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.content_api_service.main import create_app
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.digest import Digest
from app.models.digest_item import DigestItem
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source
from app.schemas.source import SourceResponse
from app.testing.schema import stamp_schema_head


def build_client() -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    delegated: dict[str, object] = {}

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command) -> SourceResponse:
            delegated["source_url"] = command.url
            return SourceResponse(
                id=8,
                display_name="Delegated",
                original_url="https://example.com",
                feed_url="https://example.com/feed.xml",
                strategy_kind="feed",
                active=True,
                status="ready",
                post_count=0,
                last_success_at=None,
                last_failure_at=None,
                needs_readaptation=False,
                readaptation_reason=None,
            )

    class FakeDeliveryServiceClient:
        def send_test_email(self) -> dict[str, str]:
            delegated["test_email"] = True
            return {"status": "sent"}

    app = create_app(
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
        delivery_service_client_factory=lambda: FakeDeliveryServiceClient(),
    )
    app.state.delegated = delegated
    return TestClient(app), session_factory


def test_content_api_service_health_and_boundary_delegation() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="Alpha Post",
                published_at=datetime(2026, 4, 26, 9, 0, tzinfo=UTC),
                raw_content="Alpha content",
                content_hash="alpha-hash",
                ingest_metadata="{}",
            )
        )
        session.add(
            PostAnalysis(
                post_id=1,
                summary_ru="Stable summary",
                metadata_json='{"topics":["verification"],"format":"article","technical_depth":"medium","verdict":"interesting","verdict_reason":"Useful signal"}',
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))

    health_response = client.get("/api/health")
    assert health_response.status_code == 200

    source_response = client.post("/api/sources", json={"url": "example.com"})
    assert source_response.status_code == 201
    assert source_response.json()["id"] == 8

    test_email_response = client.post("/api/settings/test-email")
    assert test_email_response.status_code == 200
    assert test_email_response.json() == {"status": "sent"}

    posts_response = client.get("/api/posts?window=all")
    assert posts_response.status_code == 200
    assert posts_response.json()[0]["title"] == "Alpha Post"


def test_content_api_service_lists_sent_daily_and_weekly_digests_newest_first() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="First Post",
                published_at=datetime(2026, 4, 26, 9, 0, tzinfo=UTC),
                raw_content="Alpha content",
                content_hash="alpha-hash",
                ingest_metadata="{}",
            )
        )
        session.add(
            Post(
                id=2,
                source_id=1,
                canonical_url="https://alpha.example/posts/2",
                title="Second Post",
                published_at=datetime(2026, 4, 26, 10, 0, tzinfo=UTC),
                raw_content="Beta content",
                content_hash="beta-hash",
                ingest_metadata="{}",
            )
        )
        session.add_all(
            [
                Digest(
                    id=10,
                    digest_type="daily",
                    scheduled_for=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
                    status="sent",
                    recipient_email="reader@example.com",
                    subject="Good News digest for 2026-04-25",
                    html_body="<html>older</html>",
                    sent_at=datetime(2026, 4, 25, 12, 5, tzinfo=UTC),
                ),
                Digest(
                    id=11,
                    digest_type="weekly",
                    scheduled_for=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                    status="sent",
                    recipient_email="reader@example.com",
                    subject="Weekly digest",
                    html_body="<html>weekly</html>",
                    sent_at=datetime(2026, 4, 26, 12, 5, tzinfo=UTC),
                ),
                Digest(
                    id=12,
                    digest_type="daily",
                    scheduled_for=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
                    status="skipped",
                    recipient_email=None,
                    subject="Good News digest for 2026-04-27",
                    html_body="<html>newer</html>",
                    sent_at=None,
                ),
                Digest(
                    id=13,
                    digest_type="operator",
                    scheduled_for=datetime(2026, 4, 26, 13, 0, tzinfo=UTC),
                    status="sent",
                    recipient_email="ops@example.com",
                    subject="Operator digest",
                    html_body="<html>operator</html>",
                    sent_at=datetime(2026, 4, 26, 13, 5, tzinfo=UTC),
                ),
            ]
        )
        session.add_all(
            [
                DigestItem(digest_id=10, post_id=1, rank_position=1),
                DigestItem(digest_id=10, post_id=2, rank_position=2),
                DigestItem(digest_id=12, post_id=2, rank_position=1),
            ]
        )

    response = client.get("/api/digests")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 11,
            "digest_type": "weekly",
            "status": "sent",
            "sent_at": "2026-04-26T12:05:00Z",
            "included_post_count": 0,
        },
        {
            "id": 10,
            "digest_type": "daily",
            "status": "sent",
            "sent_at": "2026-04-25T12:05:00Z",
            "included_post_count": 2,
        },
    ]


def test_content_api_service_returns_persisted_daily_digest_detail() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="First Post",
                published_at=datetime(2026, 4, 26, 9, 0, tzinfo=UTC),
                raw_content="Alpha content",
                content_hash="alpha-hash",
                ingest_metadata="{}",
            )
        )
        session.add(
            Post(
                id=2,
                source_id=1,
                canonical_url="https://alpha.example/posts/2",
                title="Second Post",
                published_at=datetime(2026, 4, 26, 10, 0, tzinfo=UTC),
                raw_content="Beta content",
                content_hash="beta-hash",
                ingest_metadata="{}",
            )
        )
        session.add(Feedback(post_id=1, state="want_to_read"))
        session.add(Feedback(post_id=2, state="interesting"))
        session.add(
            Digest(
                id=21,
                digest_type="daily",
                scheduled_for=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                status="sent",
                recipient_email="reader@example.com",
                subject="Good News digest for 2026-04-26",
                html_body="<html><body><h1>Good News digest for 2026-04-26</h1></body></html>",
                sent_at=datetime(2026, 4, 26, 12, 5, tzinfo=UTC),
            )
        )
        session.add_all(
            [
                DigestItem(digest_id=21, post_id=2, rank_position=1),
                DigestItem(digest_id=21, post_id=1, rank_position=2),
            ]
        )

    response = client.get("/api/digests/21")

    assert response.status_code == 200
    assert response.json() == {
        "id": 21,
        "digest_type": "daily",
        "status": "sent",
        "sent_at": "2026-04-26T12:05:00Z",
        "title": "Good News digest for 2026-04-26",
        "included_posts": [
            {"post_id": 2, "title": "Second Post", "feedback_state": "interesting"},
            {"post_id": 1, "title": "First Post", "feedback_state": "want_to_read"},
        ],
        "rendered_html": "<html><body><h1>Good News digest for 2026-04-26</h1></body></html>",
    }


def test_content_api_service_returns_persisted_weekly_digest_detail() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="Weekly Post",
                published_at=datetime(2026, 4, 26, 9, 0, tzinfo=UTC),
                raw_content="Alpha content",
                content_hash="alpha-hash",
                ingest_metadata="{}",
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))
        session.add(
            Digest(
                id=22,
                digest_type="weekly",
                scheduled_for=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
                status="sent",
                recipient_email="reader@example.com",
                subject="Good News weekly digest for 2026-04-26",
                html_body="<html><body><h1>Good News weekly digest for 2026-04-26</h1></body></html>",
                sent_at=datetime(2026, 4, 26, 12, 5, tzinfo=UTC),
            )
        )
        session.add(DigestItem(digest_id=22, post_id=1, rank_position=1))

    response = client.get("/api/digests/22")

    assert response.status_code == 200
    assert response.json() == {
        "id": 22,
        "digest_type": "weekly",
        "status": "sent",
        "sent_at": "2026-04-26T12:05:00Z",
        "title": "Good News weekly digest for 2026-04-26",
        "included_posts": [
            {"post_id": 1, "title": "Weekly Post", "feedback_state": "interesting"},
        ],
        "rendered_html": "<html><body><h1>Good News weekly digest for 2026-04-26</h1></body></html>",
    }


def test_content_api_service_returns_404_for_missing_daily_digest_detail() -> None:
    client, _ = build_client()

    response = client.get("/api/digests/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Digest not found"}


def test_content_api_service_returns_404_for_non_sent_daily_digest_detail() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(
            Digest(
                id=31,
                digest_type="daily",
                scheduled_for=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
                status="skipped",
                recipient_email=None,
                subject="Good News digest for 2026-04-27",
                html_body="<html>not sent</html>",
                sent_at=None,
            )
        )

    response = client.get("/api/digests/31")

    assert response.status_code == 404
    assert response.json() == {"detail": "Digest not found"}


def test_content_api_service_returns_404_for_non_product_digest_detail() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(
            Digest(
                id=41,
                digest_type="operator",
                scheduled_for=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
                status="sent",
                recipient_email="ops@example.com",
                subject="Operator digest",
                html_body="<html>operator</html>",
                sent_at=datetime(2026, 4, 27, 12, 5, tzinfo=UTC),
            )
        )

    response = client.get("/api/digests/41")

    assert response.status_code == 404
    assert response.json() == {"detail": "Digest not found"}


def test_content_api_service_excludes_observability_daily_digests_from_product_history() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(
            Digest(
                id=51,
                digest_type="observability_daily",
                scheduled_for=datetime(2026, 4, 28, 18, 0, tzinfo=timezone.utc),
                status="sent",
                recipient_email="ops@example.com",
                subject="Good News observability report for 2026-04-28",
                html_body="<html><body>ops</body></html>",
                sent_at=datetime(2026, 4, 28, 18, 0, tzinfo=timezone.utc),
            )
        )

    list_response = client.get("/api/digests")
    detail_response = client.get("/api/digests/51")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert detail_response.status_code == 404
    assert detail_response.json() == {"detail": "Digest not found"}
