from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.content_api_service.main import create_app
from app.main import create_app as create_monolith_app
from app.models.base import Base
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source
from app.testing.schema import stamp_schema_head


def build_client() -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    app = create_app(session_factory=session_factory)
    return TestClient(app), session_factory


def test_monitoring_summary_returns_zeros_on_empty_db() -> None:
    client, _ = build_client()

    response = client.get("/api/monitoring/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["sources_active"] == 0
    assert data["sources_total"] == 0
    assert data["posts_total"] == 0
    assert data["last_sync_at"] is None


def test_monitoring_summary_returns_counts() -> None:
    client, session_factory = build_client()

    last_sync = datetime(2026, 5, 15, 10, 0, 0, tzinfo=timezone.utc)

    with session_scope(session_factory) as session:
        source_active = Source(
            display_name="Active Source",
            original_url="https://active.example",
            active=True,
            status="ready",
            last_success_at=last_sync,
        )
        source_inactive = Source(
            display_name="Inactive Source",
            original_url="https://inactive.example",
            active=False,
            status="ready",
            last_success_at=None,
        )
        session.add(source_active)
        session.add(source_inactive)
        session.flush()

        post1 = Post(
            source_id=source_active.id,
            canonical_url="https://active.example/post/1",
            title="Post One",
            raw_content="Content one",
            content_hash="hash1",
            ingest_metadata="{}",
        )
        post2 = Post(
            source_id=source_active.id,
            canonical_url="https://active.example/post/2",
            title="Post Two",
            raw_content="Content two",
            content_hash="hash2",
            ingest_metadata="{}",
        )
        session.add(post1)
        session.add(post2)

    response = client.get("/api/monitoring/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["sources_active"] == 1
    assert data["sources_total"] == 2
    assert data["posts_total"] == 2
    assert data["last_sync_at"] == "2026-05-15T10:00:00Z"


def test_monitoring_summary_last_sync_is_max_of_all_sources() -> None:
    client, session_factory = build_client()

    older = datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)

    with session_scope(session_factory) as session:
        session.add(Source(
            display_name="Old",
            original_url="https://old.example",
            active=True,
            status="ready",
            last_success_at=older,
        ))
        session.add(Source(
            display_name="New",
            original_url="https://new.example",
            active=True,
            status="ready",
            last_success_at=newer,
        ))

    response = client.get("/api/monitoring/summary")

    assert response.status_code == 200
    assert response.json()["last_sync_at"] == "2026-05-14T12:00:00Z"
    assert response.json()["sources_active"] == 2
    assert response.json()["sources_total"] == 2


def _seed_post(session, post_id: int) -> None:
    session.add(Source(id=post_id, display_name=f"S{post_id}", original_url=f"https://s{post_id}.example", status="ready"))
    session.add(
        Post(
            id=post_id,
            source_id=post_id,
            canonical_url=f"https://s{post_id}.example/p",
            title=f"Post {post_id}",
            published_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            raw_content="Body.",
            content_hash=f"hash-{post_id}",
            ingest_metadata='{"strategy":"feed"}',
        )
    )


def test_analyze_now_drains_pending_queue() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    with session_scope(session_factory) as session:
        _seed_post(session, 1)
        _seed_post(session, 2)

    class FakePersistingClient:
        def __init__(self, factory: object) -> None:
            self._factory = factory

        def analyze_and_persist(self, request: object) -> None:
            with session_scope(self._factory) as session:
                session.add(PostAnalysis(post_id=request.post_id, summary_ru="x", metadata_json="{}"))
                session.commit()

    app = create_monolith_app(
        session_factory=session_factory,
        document_loader=lambda url: None,
        analysis_client_factory=lambda: FakePersistingClient(session_factory),
    )
    client = TestClient(app)

    response = client.post("/api/monitoring/analyze-now")

    assert response.status_code == 200
    assert response.json() == {"analyzed": 2, "remaining": 0}

    summary = client.get("/api/monitoring/summary")
    assert summary.json()["posts_unranked"] == 0
