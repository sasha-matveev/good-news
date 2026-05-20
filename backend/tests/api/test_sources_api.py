from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.content_api_service.main import create_app
from app.models.base import Base
from app.models.post import Post
from app.models.source import Source
from app.schemas.source import SourceResponse
from app.services.ingestion_boundary import (
    DuplicateSourceError as BoundaryDuplicateSourceError,
    SourceOnboardingCommand,
    accept_source_onboarding_command,
)
from app.services.source_ingestion_service_client import DuplicateSourceError as ServiceDuplicateSourceError
from app.source_ingestion_service.main import create_app as create_source_ingestion_app
from app.testing.schema import stamp_schema_head


def _build_feed_document(*, total_items: int, newest_first: bool = True) -> str:
    item_numbers = range(total_items, 0, -1) if newest_first else range(1, total_items + 1)
    items = []
    for item_number in item_numbers:
        published_day = f"{item_number:02d}"
        items.append(
            f"""
            <item>
              <title>Post {item_number}</title>
              <link>https://heavy.example/posts/{item_number}</link>
              <pubDate>2026-04-{published_day}T10:00:00+00:00</pubDate>
              <description>Excerpt {item_number}</description>
            </item>
            """
        )
    return f"<rss><channel>{''.join(items)}</channel></rss>"


def build_client() -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    discovery_responses = {
        "https://example.com": """
        <html>
          <head><title>Example</title></head>
          <body>
            <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
          </body>
        </html>
        """
    }

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command: SourceOnboardingCommand) -> SourceResponse:
            with session_scope(session_factory) as session:
                try:
                    source = accept_source_onboarding_command(
                        session=session,
                        command=command,
                        responses=discovery_responses,
                    )
                except BoundaryDuplicateSourceError as exc:
                    raise ServiceDuplicateSourceError(str(exc)) from exc
            return SourceResponse.from_model(source)

    app = create_app(
        session_factory=session_factory,
        discovery_responses=discovery_responses,
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
    )
    return TestClient(app), session_factory


def test_post_sources_creates_ready_source_with_feed_strategy() -> None:
    client, _ = build_client()

    response = client.post("/api/sources", json={"url": "example.com"})

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "display_name": "Example",
        "original_url": "https://example.com",
        "feed_url": "https://example.com/feed.xml",
        "strategy_kind": "feed",
        "active": True,
        "status": "ready",
        "post_count": 0,
        "last_success_at": None,
        "last_failure_at": None,
        "needs_readaptation": False,
        "readaptation_reason": None,
    }


def test_get_sources_lists_existing_source_state() -> None:
    client, session_factory = build_client()
    last_success = datetime(2026, 4, 26, 8, 30, tzinfo=timezone.utc)
    last_failure = datetime(2026, 4, 26, 9, 45, tzinfo=timezone.utc)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Alpha",
                original_url="https://alpha.example",
                feed_url="https://alpha.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "common_feed_path"}',
                active=False,
                status="needs_readaptation",
                last_success_at=last_success,
                last_failure_at=last_failure,
                needs_readaptation=True,
                readaptation_reason="feed parse failed",
            )
        )

    response = client.get("/api/sources")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "display_name": "Alpha",
            "original_url": "https://alpha.example",
            "feed_url": "https://alpha.example/feed.xml",
            "strategy_kind": "feed",
            "active": False,
            "status": "needs_readaptation",
            "post_count": 0,
            "last_success_at": "2026-04-26T08:30:00Z",
            "last_failure_at": "2026-04-26T09:45:00Z",
            "needs_readaptation": True,
            "readaptation_reason": "feed parse failed",
        }
    ]


def test_patch_sources_toggles_active_state() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(display_name="Alpha", original_url="https://alpha.example", status="ready"))

    response = client.patch("/api/sources/1", json={"active": False})

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert response.json()["status"] == "ready"


def test_post_sources_returns_readaptation_needed_when_only_html_strategy_exists() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    discovery_responses = {
        "https://journal.example": """
        <html>
          <head><title>Journal</title></head>
          <body>
            <main>
              <article><h2><a href="/one">One</a></h2></article>
              <article><h2><a href="/two">Two</a></h2></article>
            </main>
          </body>
        </html>
        """
    }

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command: SourceOnboardingCommand) -> SourceResponse:
            with session_scope(session_factory) as session:
                source = accept_source_onboarding_command(
                    session=session,
                    command=command,
                    responses=discovery_responses,
                )
            return SourceResponse.from_model(source)

    app = create_app(
        session_factory=session_factory,
        discovery_responses=discovery_responses,
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
    )
    client = TestClient(app)

    response = client.post("/api/sources", json={"url": "journal.example"})

    assert response.status_code == 201
    assert response.json()["strategy_kind"] == "html"
    assert response.json()["status"] == "needs_readaptation"
    assert response.json()["needs_readaptation"] is True
    assert response.json()["readaptation_reason"] == "No usable feed discovered; HTML fallback requires monitoring."


def test_post_sources_uses_path_scoped_common_feed_for_section_sources() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    discovery_responses = {
        "https://spring.example/blog": """
        <html>
          <head><title>Spring Blog</title></head>
          <body></body>
        </html>
        """,
        "https://spring.example/blog/feed": """
        <?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0"><channel><title>Spring Blog Feed</title></channel></rss>
        """,
    }

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command: SourceOnboardingCommand) -> SourceResponse:
            with session_scope(session_factory) as session:
                source = accept_source_onboarding_command(
                    session=session,
                    command=command,
                    responses=discovery_responses,
                )
            return SourceResponse.from_model(source)

    app = create_app(
        session_factory=session_factory,
        discovery_responses=discovery_responses,
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
    )
    client = TestClient(app)

    response = client.post("/api/sources", json={"url": "https://spring.example/blog"})

    assert response.status_code == 201
    assert response.json()["original_url"] == "https://spring.example/blog"
    assert response.json()["feed_url"] == "https://spring.example/blog/feed"
    assert response.json()["strategy_kind"] == "feed"
    assert response.json()["status"] == "ready"


def test_post_sources_returns_conflict_for_duplicate_normalized_url() -> None:
    client, _ = build_client()

    first_response = client.post("/api/sources", json={"url": "example.com"})
    duplicate_response = client.post("/api/sources", json={"url": "https://example.com"})

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "Source already exists for normalized URL https://example.com"
    }


def test_post_sources_delegates_to_source_ingestion_service() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    delegated: dict[str, object] = {}

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command) -> SourceResponse:
            delegated["url"] = command.url
            return SourceResponse(
                id=7,
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

    app = create_app(
        session_factory=session_factory,
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
    )
    client = TestClient(app)

    response = client.post("/api/sources", json={"url": "example.com"})

    assert response.status_code == 201
    assert delegated["url"] == "example.com"
    assert response.json()["id"] == 7


def test_post_sources_sync_delegates_run_once_to_source_ingestion_service() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    delegated: dict[str, object] = {}

    class FakeSourceIngestionServiceClient:
        def run_sync_once(self) -> list[int]:
            delegated["called"] = True
            return [3, 5]

    app = create_app(
        session_factory=session_factory,
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
    )
    client = TestClient(app)

    response = client.post("/api/sources/sync")

    assert response.status_code == 200
    assert delegated == {"called": True}
    assert response.json() == {"processed_source_ids": [3, 5]}


def test_public_sources_api_onboards_and_syncs_yegor_through_ingestion_service() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    def document_loader(url: str) -> str | None:
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

    ingestion_app = create_source_ingestion_app(
        session_factory=session_factory,
        responses={},
        document_loader=document_loader,
        settings=Settings(source_ingestion_service_port=8200),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc),
    )
    ingestion_client = TestClient(ingestion_app)

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command: SourceOnboardingCommand) -> SourceResponse:
            response = ingestion_client.post(
                "/internal/ingestion/onboarding-commands",
                json={"url": command.url},
            )
            response.raise_for_status()
            return SourceResponse.model_validate(response.json())

        def run_sync_once(self) -> list[int]:
            response = ingestion_client.post("/internal/ingestion/sync/run-once")
            response.raise_for_status()
            return list(response.json()["processed_source_ids"])

    app = create_app(
        session_factory=session_factory,
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
    )
    client = TestClient(app)

    create_response = client.post("/api/sources", json={"url": "https://www.yegor256.com/"})
    assert create_response.status_code == 201
    assert create_response.json()["original_url"] == "https://www.yegor256.com"
    assert create_response.json()["feed_url"] == "https://www.yegor256.com/rss.xml"

    sync_response = client.post("/api/sources/sync")
    assert sync_response.status_code == 200
    assert sync_response.json() == {"processed_source_ids": [1]}

    list_response = client.get("/api/sources")
    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": 1,
            "display_name": "Yegor's Blog About Computers",
            "original_url": "https://www.yegor256.com",
            "feed_url": "https://www.yegor256.com/rss.xml",
            "strategy_kind": "feed",
            "active": True,
            "status": "ready",
            "post_count": 1,
            "last_success_at": "2026-05-11T08:00:00Z",
            "last_failure_at": None,
            "needs_readaptation": False,
            "readaptation_reason": None,
        }
    ]


def test_public_sources_api_sync_bounds_initial_heavy_feed_backlog() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    def document_loader(url: str) -> str | None:
        if url == "https://heavy.example":
            return """
            <html>
              <head>
                <title>Heavy Example</title>
                <link rel="alternate" type="application/rss+xml" href="https://heavy.example/feed.xml">
              </head>
            </html>
            """
        if url == "https://heavy.example/feed.xml":
            return _build_feed_document(total_items=30, newest_first=False)
        return None

    class FakeAnalysisServiceClient:
        def analyze_and_persist(self, request) -> None:
            return None

    ingestion_app = create_source_ingestion_app(
        session_factory=session_factory,
        responses={},
        document_loader=document_loader,
        analysis_service_client_factory=lambda: FakeAnalysisServiceClient(),
        settings=Settings(source_ingestion_service_port=8200),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 4, 30, 10, 0, tzinfo=timezone.utc),
    )
    ingestion_client = TestClient(ingestion_app)

    class FakeSourceIngestionServiceClient:
        def onboard_source(self, command: SourceOnboardingCommand) -> SourceResponse:
            response = ingestion_client.post(
                "/internal/ingestion/onboarding-commands",
                json={"url": command.url},
            )
            response.raise_for_status()
            return SourceResponse.model_validate(response.json())

        def run_sync_once(self) -> list[int]:
            response = ingestion_client.post("/internal/ingestion/sync/run-once")
            response.raise_for_status()
            return list(response.json()["processed_source_ids"])

    app = create_app(
        session_factory=session_factory,
        source_ingestion_client_factory=lambda: FakeSourceIngestionServiceClient(),
    )
    client = TestClient(app)

    create_response = client.post("/api/sources", json={"url": "https://heavy.example/"})
    assert create_response.status_code == 201

    sync_response = client.post("/api/sources/sync")
    assert sync_response.status_code == 200
    assert sync_response.json() == {"processed_source_ids": [1]}

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post).order_by(Post.published_at.desc(), Post.id.desc())).all()

    assert len(posts) == 25
    assert posts[0].canonical_url == "https://heavy.example/posts/30"
    assert posts[-1].canonical_url == "https://heavy.example/posts/6"


def test_reload_posts_endpoint_reloads_recent_posts_and_returns_counts() -> None:
    from datetime import UTC, datetime, timedelta
    from app.models.feedback import Feedback

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    with session_scope(session_factory) as session:
        now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
        session.add(
            Source(
                id=1,
                display_name="Blog",
                original_url="https://blog.example",
                feed_url="https://blog.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                last_success_at=now - timedelta(days=1),
            )
        )
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://blog.example/posts/recent",
                title="Recent",
                published_at=now - timedelta(days=3),
                raw_content="Old recent content.",
                content_hash="recent",
                ingest_metadata='{"date_source":"feed","source_strategy":"feed"}',
                created_at=now - timedelta(days=3),
            )
        )
        session.add(
            Post(
                id=2,
                source_id=1,
                canonical_url="https://blog.example/posts/old",
                title="Old",
                published_at=now - timedelta(days=120),
                raw_content="Old stable content.",
                content_hash="old",
                ingest_metadata='{"date_source":"feed","source_strategy":"feed"}',
                created_at=now - timedelta(days=120),
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))

    app = create_app(session_factory=session_factory, discovery_responses={})
    app.state.now_provider = lambda: now
    app.state.responses = {
        "https://blog.example/feed.xml": """
        <rss>
          <channel>
            <item>
              <title>Recent replacement</title>
              <link>https://blog.example/posts/recent</link>
              <pubDate>2026-05-18T09:00:00+00:00</pubDate>
              <description>Reloaded content.</description>
            </item>
            <item>
              <title>Brand new</title>
              <link>https://blog.example/posts/new</link>
              <pubDate>2026-05-19T09:00:00+00:00</pubDate>
              <description>Brand new content.</description>
            </item>
          </channel>
        </rss>
        """
    }
    client = TestClient(app)
    response = client.post("/api/sources/1/reload-posts")

    assert response.status_code == 200
    body = response.json()
    assert body == {"deleted": 1, "reloaded": 2}

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post).where(Post.source_id == 1).order_by(Post.canonical_url)).all()
        feedback = session.scalars(select(Feedback).order_by(Feedback.post_id)).all()
    assert [post.canonical_url for post in posts] == [
        "https://blog.example/posts/new",
        "https://blog.example/posts/old",
        "https://blog.example/posts/recent",
    ]
    assert feedback == []


def test_reload_posts_endpoint_returns_404_for_missing_source() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    app = create_app(session_factory=session_factory, discovery_responses={})
    client = TestClient(app)
    response = client.post("/api/sources/999/reload-posts")
    assert response.status_code == 404
