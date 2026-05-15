from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.content_api_service.main import create_app
from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source
from app.schemas.source import SourceResponse
from app.testing.schema import stamp_schema_head


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured for this integration run.")
    return value


def _reset_runtime_state(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.execute(text("DELETE FROM digest_items"))
        session.execute(text("DELETE FROM digests"))
        session.execute(text("DELETE FROM feedback"))
        session.execute(text("DELETE FROM post_analysis"))
        session.execute(text("DELETE FROM posts"))
        session.execute(text("DELETE FROM technical_events"))
        session.execute(text("DELETE FROM sources"))


def test_content_api_service_runtime_preserves_frontend_contracts_and_delegates_to_extracted_services() -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    unique_url = f"https://content-api-runtime.example/{uuid4()}"
    delegated: dict[str, object] = {}

    _reset_runtime_state(session_factory)

    with session_scope(session_factory) as session:
        source = Source(display_name="Runtime", original_url=unique_url, status="ready")
        session.add(source)
        session.flush()
        post = Post(
            source_id=source.id,
            canonical_url=f"{unique_url}/post",
            title="Content API Runtime Post",
            published_at=datetime(2026, 4, 26, 9, 0, tzinfo=UTC),
            raw_content="Runtime content",
            content_hash=f"content-api-{uuid4()}",
            ingest_metadata="{}",
        )
        session.add(post)
        session.flush()
        session.add(
            PostAnalysis(
                post_id=post.id,
                summary_ru="Runtime content-api summary",
                metadata_json='{"topics":["runtime"],"format":"article","technical_depth":"medium","verdict":"interesting","verdict_reason":"Runtime content-api proof."}',
            )
        )
        session.add(Feedback(post_id=post.id, state="want_to_read"))

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command) -> SourceResponse:
            delegated["source_url"] = command.url
            return SourceResponse(
                id=21,
                display_name="Delegated Runtime",
                original_url="https://delegated-runtime.example",
                feed_url="https://delegated-runtime.example/feed.xml",
                strategy_kind="feed",
                active=True,
                status="ready",
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
        settings=Settings.from_env(),
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
        delivery_service_client_factory=lambda: FakeDeliveryServiceClient(),
    )
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    assert client.post("/api/settings/test-email").json() == {"status": "sent"}
    assert client.post("/api/sources", json={"url": "delegated-runtime.example"}).status_code == 201
    posts_response = client.get("/api/posts?window=all")
    assert posts_response.status_code == 200
    assert posts_response.json()[0]["title"] == "Content API Runtime Post"
    assert delegated == {"test_email": True, "source_url": "delegated-runtime.example"}
