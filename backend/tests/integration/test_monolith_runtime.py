from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.main import create_app
from app.models.post import Post
from app.models.source import Source
from app.testing.schema import stamp_schema_head


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured for this integration run.")
    return value


def _reset_runtime_state(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.execute(text("DELETE FROM post_analysis"))
        session.execute(text("DELETE FROM posts"))
        session.execute(text("DELETE FROM technical_events"))
        session.execute(text("DELETE FROM sources"))


def test_monolith_runtime_onboards_and_syncs_source_directly() -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    unique_url = f"https://monolith-runtime.example/{uuid4()}"
    unique_post_url = f"{unique_url}/post"

    _reset_runtime_state(session_factory)

    class FakeAnalysisClient:
        def analyze_and_persist(self, request) -> None:
            return None

    responses = {
        unique_url: f"""
        <html>
          <head><title>Monolith Runtime Source</title></head>
          <body>
            <link rel="alternate" type="application/rss+xml" href="{unique_url}/feed.xml" />
          </body>
        </html>
        """,
        f"{unique_url}/feed.xml": f"""
        <rss>
          <channel>
            <item>
              <title>Monolith Runtime Post</title>
              <link>{unique_post_url}</link>
              <pubDate>2026-05-16T10:00:00+00:00</pubDate>
              <description>Monolith direct ingestion content.</description>
            </item>
          </channel>
        </rss>
        """,
    }

    app = create_app(
        session_factory=session_factory,
        settings=settings,
        responses=responses,
        analysis_client_factory=lambda: FakeAnalysisClient(),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
    )
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200

    create_response = client.post("/api/sources", json={"url": unique_url})
    assert create_response.status_code == 201
    assert create_response.json()["original_url"] == unique_url

    sync_response = client.post("/api/sources/sync")
    assert sync_response.status_code == 200
    assert create_response.json()["id"] in sync_response.json()["processed_source_ids"]

    with session_scope(session_factory) as session:
        saved_source = session.scalar(select(Source).where(Source.original_url == unique_url))
        saved_post = session.scalar(select(Post).where(Post.canonical_url == unique_post_url))

    assert saved_source is not None
    assert saved_post is not None
    assert saved_post.title == "Monolith Runtime Post"
