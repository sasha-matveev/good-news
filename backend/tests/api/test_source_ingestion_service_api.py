from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.post import Post
from app.models.source import Source
from app.source_ingestion_service.main import _build_live_document_loader, create_app
from app.testing.schema import stamp_schema_head


class FakeAnalysisServiceClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | int]] = []

    def analyze_and_persist(self, request) -> None:
        self.calls.append({"post_id": request.post_id, "title": request.title, "content": request.content})


def build_client(*, responses: dict[str, str]) -> tuple[TestClient, object, FakeAnalysisServiceClient]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    fake_analysis_client = FakeAnalysisServiceClient()
    app = create_app(
        session_factory=session_factory,
        responses=responses,
        analysis_service_client_factory=lambda: fake_analysis_client,
        settings=Settings(source_ingestion_service_port=8200),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 4, 26, 10, 0, tzinfo=UTC),
    )
    return TestClient(app), session_factory, fake_analysis_client


def build_client_with_document_loader(
    *,
    document_loader,
) -> tuple[TestClient, object, FakeAnalysisServiceClient]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    fake_analysis_client = FakeAnalysisServiceClient()
    app = create_app(
        session_factory=session_factory,
        responses={},
        document_loader=document_loader,
        analysis_service_client_factory=lambda: fake_analysis_client,
        settings=Settings(source_ingestion_service_port=8200),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 11, 8, 0, tzinfo=UTC),
    )
    return TestClient(app), session_factory, fake_analysis_client


def test_source_ingestion_service_health_onboarding_and_sync() -> None:
    client, session_factory, fake_analysis_client = build_client(
        responses={
            "https://example.com": """
            <html>
              <head><title>Example</title></head>
              <body>
                <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
              </body>
            </html>
            """,
            "https://example.com/feed.xml": """
            <rss>
              <channel>
                <item>
                  <title>Alpha One</title>
                  <link>https://example.com/posts/1</link>
                  <pubDate>2026-04-26T10:00:00+00:00</pubDate>
                  <description>First useful excerpt.</description>
                </item>
              </channel>
            </rss>
            """,
        }
    )

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    onboarding_response = client.post("/internal/ingestion/onboarding-commands", json={"url": "example.com"})
    assert onboarding_response.status_code == 200
    assert onboarding_response.json() == {
        "id": 1,
        "display_name": "Example",
        "original_url": "https://example.com",
        "feed_url": "https://example.com/feed.xml",
        "strategy_kind": "feed",
        "active": True,
        "status": "ready",
        "last_success_at": None,
        "last_failure_at": None,
        "needs_readaptation": False,
        "readaptation_reason": None,
    }

    sync_response = client.post("/internal/ingestion/sync/run-once")
    assert sync_response.status_code == 200
    assert sync_response.json() == {"processed_source_ids": [1]}
    assert fake_analysis_client.calls == [
        {
            "post_id": 1,
            "title": "Alpha One",
            "content": "First useful excerpt.",
        }
    ]

    with session_scope(session_factory) as session:
        source = session.get(Source, 1)
        posts = session.scalars(select(Post).order_by(Post.id)).all()

    assert source is not None
    assert source.last_success_at == datetime(2026, 4, 26, 10, 0)
    assert [post.canonical_url for post in posts] == ["https://example.com/posts/1"]


def test_source_ingestion_service_onboards_and_syncs_live_documents_without_stub_map() -> None:
    requested_urls: list[str] = []

    def document_loader(url: str) -> str | None:
        requested_urls.append(url)
        if url == "https://www.yegor256.com":
            return """
            <html>
              <head>
                <title>Yegor's Blog About Computers</title>
                <link rel="alternate" type="application/rss+xml" href="https://www.yegor256.com/rss.xml">
              </head>
            </html>
            """
        if url == "https://www.yegor256.com/rss.xml":
            return """
            <rss version="2.0">
              <channel>
                <item>
                  <title>Couriers, Not Coders</title>
                  <link>https://www.yegor256.com/2026/05/03/couriers-not-coders.html</link>
                  <pubDate>Sun, 03 May 2026 00:00:00 GMT</pubDate>
                  <description>Someone submitted an issue to one of our open GitHub repositories.</description>
                </item>
              </channel>
            </rss>
            """
        return None

    client, session_factory, fake_analysis_client = build_client_with_document_loader(
        document_loader=document_loader
    )

    onboarding_response = client.post(
        "/internal/ingestion/onboarding-commands",
        json={"url": "https://www.yegor256.com/"},
    )
    assert onboarding_response.status_code == 200
    assert onboarding_response.json()["original_url"] == "https://www.yegor256.com"
    assert onboarding_response.json()["feed_url"] == "https://www.yegor256.com/rss.xml"
    assert onboarding_response.json()["status"] == "ready"

    sync_response = client.post("/internal/ingestion/sync/run-once")
    assert sync_response.status_code == 200
    assert sync_response.json() == {"processed_source_ids": [1]}

    with session_scope(session_factory) as session:
        source = session.get(Source, 1)
        posts = session.scalars(select(Post).order_by(Post.id)).all()

    assert source is not None
    assert source.original_url == "https://www.yegor256.com"
    assert [post.canonical_url for post in posts] == [
        "https://www.yegor256.com/2026/05/03/couriers-not-coders.html"
    ]
    assert fake_analysis_client.calls == [
        {
            "post_id": 1,
            "title": "Couriers, Not Coders",
            "content": "Someone submitted an issue to one of our open GitHub repositories.",
        }
    ]
    assert requested_urls == [
        "https://www.yegor256.com",
        "https://www.yegor256.com/rss.xml",
        "https://www.yegor256.com/rss.xml",
    ]


def test_live_document_loader_returns_none_for_http_errors() -> None:
    class FakeClient:
        def get(self, url: str) -> object:
            request = httpx.Request("GET", url)
            response = httpx.Response(status_code=404, request=request)

            class FakeResponse:
                text = "missing"

                def raise_for_status(self) -> None:
                    raise httpx.HTTPStatusError("not found", request=request, response=response)

            return FakeResponse()

    loader = _build_live_document_loader(FakeClient())  # type: ignore[arg-type]

    assert loader("https://missing.example") is None


def test_live_document_loader_retries_transient_tls_eof_connect_failures() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, url: str) -> object:
            self.calls += 1
            if self.calls == 1:
                raise httpx.ConnectError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")

            class FakeResponse:
                text = "<rss></rss>"

                def raise_for_status(self) -> None:
                    return None

            return FakeResponse()

    client = FakeClient()
    loader = _build_live_document_loader(client)  # type: ignore[arg-type]

    assert loader("https://www.yegor256.com/rss.xml") == "<rss></rss>"
    assert client.calls == 2


def test_source_ingestion_service_startup_keeps_default_tls_verification(monkeypatch) -> None:
    captured_kwargs: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

        def get(self, url: str) -> httpx.Response:
            return httpx.Response(200, request=httpx.Request("GET", url), text="<html></html>")

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.source_ingestion_service.main.httpx.Client", FakeClient)

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    app = create_app(
        session_factory=session_factory,
        responses={},
        settings=Settings(source_ingestion_service_port=8200),
        enable_scheduler=False,
    )

    with TestClient(app):
        assert "verify" not in captured_kwargs
        assert captured_kwargs["follow_redirects"] is True
