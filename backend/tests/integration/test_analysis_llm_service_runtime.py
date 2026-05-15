from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.analysis_llm_service.main import create_app
from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source
from app.testing.schema import stamp_schema_head


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured for this integration run.")
    return value


def test_analysis_llm_service_persists_analysis_through_service_boundary(monkeypatch) -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    unique_url = f"https://analysis-runtime.example/{uuid4()}"
    with session_scope(session_factory) as session:
        session.execute(text("DELETE FROM post_analysis"))
        session.add(Source(display_name="Runtime", original_url=unique_url, status="ready"))
        session.flush()
        source_id = session.scalar(text("SELECT id FROM sources WHERE original_url = :url"), {"url": unique_url})
        session.add(
            Post(
                source_id=source_id,
                canonical_url=f"{unique_url}/post",
                title="Runtime Post",
                published_at=None,
                raw_content="Runtime content body.",
                content_hash=f"runtime-{uuid4()}",
                ingest_metadata="{}",
            )
        )

    monkeypatch.setenv(
        "GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON",
        json.dumps(
            {
                "summary_ru": "Runtime Russian summary.",
                "topics": ["runtime"],
                "format": "article",
                "technical_depth": "medium",
                "verdict": "interesting",
                "verdict_reason": "Runtime service check.",
            }
        ),
    )
    app = create_app(session_factory=session_factory, settings=Settings.from_env())
    client = TestClient(app)

    with session_scope(session_factory) as session:
        post_id = session.query(Post.id).filter(Post.title == "Runtime Post").scalar()

    response = client.post(
        "/internal/analysis/requests",
        json={
            "post_id": post_id,
            "title": "Runtime Post",
            "content": "Runtime content body.",
        },
    )

    assert response.status_code == 200
    with session_scope(session_factory) as session:
        saved = session.query(PostAnalysis).filter(PostAnalysis.post_id == post_id).one()

    assert saved.summary_ru == "Runtime Russian summary."
