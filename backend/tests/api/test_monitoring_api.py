from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.content_api_service.main import create_app
from app.models.base import Base
from app.models.post import Post
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
