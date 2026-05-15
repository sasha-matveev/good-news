from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from app.ai.ollama_client import OllamaClient
from app.analysis_llm_service.main import create_app
from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source
from app.testing.schema import stamp_schema_head


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def analyze_article(self, title: str, content: str):
        self.calls.append({"title": title, "content": content})
        return type(
            "Payload",
            (),
            {
                "summary_ru": "Short Russian summary.",
                "topics": ["verification"],
                "format": "article",
                "technical_depth": "medium",
                "verdict": "interesting",
                "verdict_reason": "Useful boundary check.",
            },
        )()


def build_client() -> tuple[TestClient, object, FakeOllamaClient]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    fake_client = FakeOllamaClient()
    app = create_app(
        session_factory=session_factory,
        analysis_client_factory=lambda: fake_client,
        settings=Settings(analysis_service_port=8100),
    )
    return TestClient(app), session_factory, fake_client


def test_analysis_service_health_and_request_persistence() -> None:
    client, session_factory, fake_client = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=11,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=None,
                raw_content="Useful article body.",
                content_hash="alpha-one",
                ingest_metadata="{}",
            )
        )

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    response = client.post(
        "/internal/analysis/requests",
        json={
            "post_id": 11,
            "title": "Alpha One",
            "content": "Useful article body.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "summary_ru": "Short Russian summary.",
        "topics": ["verification"],
        "format": "article",
        "technical_depth": "medium",
        "verdict": "interesting",
        "verdict_reason": "Useful boundary check.",
    }
    assert fake_client.calls == [{"title": "Alpha One", "content": "Useful article body."}]

    with session_scope(session_factory) as session:
        saved = session.query(PostAnalysis).filter(PostAnalysis.post_id == 11).one()

    assert saved.summary_ru == "Short Russian summary."
    assert json.loads(saved.metadata_json)["verdict"] == "interesting"


def test_analysis_service_normalizes_nested_ollama_payloads_before_persistence() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=12,
                source_id=1,
                canonical_url="https://alpha.example/posts/two",
                title="Alpha Two",
                published_at=None,
                raw_content="Useful article body.",
                content_hash="alpha-two",
                ingest_metadata="{}",
            )
        )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "summary_ru": {"text": "Short Russian summary.", "length": 2},
                        "topics": {"name": "verification", "confidence": 0.9},
                        "format": {"kind": "article"},
                        "technical_depth": ["medium", {"level": 3}],
                        "verdict": "interesting",
                        "verdict_reason": {"detail": "Useful boundary check."},
                    }
                )
            },
        )

    app = create_app(
        session_factory=session_factory,
        analysis_client_factory=lambda: OllamaClient(
            settings=Settings(analysis_service_port=8100, ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
        settings=Settings(analysis_service_port=8100, ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
    )
    client = TestClient(app)

    response = client.post(
        "/internal/analysis/requests",
        json={
            "post_id": 12,
            "title": "Alpha Two",
            "content": "Useful article body.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "summary_ru": '{"length":2,"text":"Short Russian summary."}',
        "topics": ['{"confidence":0.9,"name":"verification"}'],
        "format": '{"kind":"article"}',
        "technical_depth": '["medium",{"level":3}]',
        "verdict": "interesting",
        "verdict_reason": '{"detail":"Useful boundary check."}',
    }

    with session_scope(session_factory) as session:
        saved = session.query(PostAnalysis).filter(PostAnalysis.post_id == 12).one()

    assert saved.summary_ru == '{"length":2,"text":"Short Russian summary."}'
    assert json.loads(saved.metadata_json) == {
        "topics": ['{"confidence":0.9,"name":"verification"}'],
        "format": '{"kind":"article"}',
        "technical_depth": '["medium",{"level":3}]',
        "verdict": "interesting",
        "verdict_reason": '{"detail":"Useful boundary check."}',
    }
