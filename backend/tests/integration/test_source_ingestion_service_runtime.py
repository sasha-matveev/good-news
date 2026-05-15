from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.models.post import Post
from app.models.setting import TechnicalEvent
from app.models.source import Source
from app.source_ingestion_service.main import create_app
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


def test_source_ingestion_service_runtime_persists_sources_and_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    unique_url = f"https://ingestion-runtime.example/{uuid4()}"
    unique_post_url = f"{unique_url}/post"

    _reset_runtime_state(session_factory)

    monkeypatch.setenv(
        "GOOD_NEWS_INGESTION_RESPONSES_JSON",
        json.dumps(
            {
                unique_url: f"""
                <html>
                  <head><title>Runtime Source</title></head>
                  <body>
                    <link rel="alternate" type="application/rss+xml" href="{unique_url}/feed.xml" />
                  </body>
                </html>
                """,
                f"{unique_url}/feed.xml": f"""
                <rss>
                  <channel>
                    <item>
                      <title>Runtime Ingestion Post</title>
                      <link>{unique_post_url}</link>
                      <pubDate>2026-04-26T10:00:00+00:00</pubDate>
                      <description>Runtime ingestion content.</description>
                    </item>
                  </channel>
                </rss>
                """,
            }
        ),
    )
    class FakeAnalysisServiceClient:
        def analyze_and_persist(self, request) -> None:
            return None

    app = create_app(
        session_factory=session_factory,
        settings=Settings.from_env(),
        enable_scheduler=False,
        analysis_service_client_factory=lambda: FakeAnalysisServiceClient(),
    )
    client = TestClient(app)

    onboarding_response = client.post("/internal/ingestion/onboarding-commands", json={"url": unique_url})
    assert onboarding_response.status_code == 200

    sync_response = client.post("/internal/ingestion/sync/run-once")
    assert sync_response.status_code == 200

    with session_scope(session_factory) as session:
        saved_source = session.scalar(select(Source).where(Source.original_url == unique_url))
        saved_post = session.scalar(select(Post).where(Post.canonical_url == unique_post_url))

    assert saved_source is not None
    assert saved_post is not None


def test_source_ingestion_service_runtime_rejects_duplicate_onboarding_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    unique_url = f"https://ingestion-runtime.example/{uuid4()}"

    _reset_runtime_state(session_factory)

    monkeypatch.setenv(
        "GOOD_NEWS_INGESTION_RESPONSES_JSON",
        json.dumps(
            {
                unique_url: f"""
                <html>
                  <head><title>Runtime Source</title></head>
                  <body>
                    <link rel="alternate" type="application/rss+xml" href="{unique_url}/feed.xml" />
                  </body>
                </html>
                """
            }
        ),
    )

    app = create_app(
        session_factory=session_factory,
        settings=Settings.from_env(),
        enable_scheduler=False,
    )
    client = TestClient(app)

    first_response = client.post("/internal/ingestion/onboarding-commands", json={"url": unique_url})
    duplicate_response = client.post("/internal/ingestion/onboarding-commands", json={"url": f"{unique_url}/"})

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": f"Source already exists for normalized URL {unique_url}"
    }


def test_source_ingestion_service_runtime_reconciles_failed_source_after_readaptation() -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    unique_url = f"https://ingestion-runtime.example/{uuid4()}"
    stale_feed_url = f"{unique_url}/feed.xml"
    reconciled_feed_url = f"{unique_url}/reconciled-feed.xml"
    reconciled_post_url = f"{unique_url}/reconciled-post"
    responses = {
        unique_url: f"""
        <html>
          <head><title>Runtime Source</title></head>
          <body>
            <link rel="alternate" type="application/rss+xml" href="{stale_feed_url}" />
          </body>
        </html>
        """
    }

    _reset_runtime_state(session_factory)

    class FakeAnalysisServiceClient:
        def analyze_and_persist(self, request) -> None:
            return None

    app = create_app(
        session_factory=session_factory,
        responses=responses,
        settings=Settings(source_failure_threshold=2),
        enable_scheduler=False,
        analysis_service_client_factory=lambda: FakeAnalysisServiceClient(),
    )
    client = TestClient(app)

    onboarding_response = client.post("/internal/ingestion/onboarding-commands", json={"url": unique_url})
    assert onboarding_response.status_code == 200

    first_sync_response = client.post("/internal/ingestion/sync/run-once")
    assert first_sync_response.status_code == 200
    assert first_sync_response.json() == {"processed_source_ids": []}

    with session_scope(session_factory) as session:
        source = session.scalar(select(Source).where(Source.original_url == unique_url))

    assert source is not None
    assert source.feed_url == stale_feed_url
    assert source.status == "failing"
    assert source.consecutive_failures == 1

    responses[unique_url] = f"""
    <html>
      <head><title>Runtime Source</title></head>
      <body>
        <link rel="alternate" type="application/rss+xml" href="{reconciled_feed_url}" />
      </body>
    </html>
    """
    responses[reconciled_feed_url] = f"""
    <rss>
      <channel>
        <item>
          <title>Reconciled Runtime Post</title>
          <link>{reconciled_post_url}</link>
          <pubDate>2026-04-26T10:00:00+00:00</pubDate>
          <description>Recovered after readaptation.</description>
        </item>
      </channel>
    </rss>
    """

    second_sync_response = client.post("/internal/ingestion/sync/run-once")
    assert second_sync_response.status_code == 200
    assert second_sync_response.json() == {"processed_source_ids": []}

    with session_scope(session_factory) as session:
        source = session.scalar(select(Source).where(Source.original_url == unique_url))
        events = session.scalars(select(TechnicalEvent).order_by(TechnicalEvent.id)).all()

    assert source is not None
    assert source.feed_url == reconciled_feed_url
    assert source.status == "ready"
    assert source.needs_readaptation is False
    assert source.readaptation_reason is None
    assert source.consecutive_failures == 0
    assert [event.event_code for event in events] == [
        "source.repeated_failure",
        "source.readaptation_needed",
    ]

    third_sync_response = client.post("/internal/ingestion/sync/run-once")
    assert third_sync_response.status_code == 200
    assert third_sync_response.json() == {"processed_source_ids": [source.id]}

    with session_scope(session_factory) as session:
        saved_post = session.scalar(select(Post).where(Post.canonical_url == reconciled_post_url))
        refreshed_source = session.scalar(select(Source).where(Source.original_url == unique_url))

    assert refreshed_source is not None
    assert refreshed_source.status == "ready"
    assert saved_post is not None
