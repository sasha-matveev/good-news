from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.setting import TechnicalEvent
from app.models.source import Source
from app.services.analysis import AnalysisResult
from app.services.source_sync import sync_active_sources


def _build_feed_document(*, total_items: int, newest_first: bool = True) -> str:
    item_numbers = range(total_items, 0, -1) if newest_first else range(1, total_items + 1)
    items = []
    for item_number in item_numbers:
        published_day = f"{item_number:02d}"
        items.append(
            f"""
            <item>
              <title>Post {item_number}</title>
              <link>https://alpha.example/posts/{item_number}</link>
              <pubDate>2026-04-{published_day}T10:00:00+00:00</pubDate>
              <description>Excerpt {item_number}</description>
            </item>
            """
        )
    return f"<rss><channel>{''.join(items)}</channel></rss>"


def test_sync_active_sources_persists_posts_and_deduplicates_by_url_then_hash() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Alpha",
                original_url="https://alpha.example",
                feed_url="https://alpha.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://alpha.example/feed.xml": """
            <rss>
              <channel>
                <item>
                  <title>Alpha One</title>
                  <link>https://alpha.example/posts/1</link>
                  <pubDate>2026-04-26T10:00:00+00:00</pubDate>
                  <description>First useful excerpt.</description>
                </item>
                <item>
                  <title>Alpha Duplicate URL</title>
                  <link>https://alpha.example/posts/1</link>
                  <pubDate>2026-04-26T10:05:00+00:00</pubDate>
                  <description>Second copy should be ignored.</description>
                </item>
                <item>
                  <title>Alpha Duplicate Hash</title>
                  <link>https://alpha.example/posts/2</link>
                  <pubDate>2026-04-26T10:10:00+00:00</pubDate>
                  <description>First useful excerpt.</description>
                </item>
              </channel>
            </rss>
            """
        },
        now=datetime(2026, 4, 26, 10, 30, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post).order_by(Post.id)).all()
        source = session.get(Source, 1)

    assert [post.canonical_url for post in posts] == ["https://alpha.example/posts/1"]
    assert posts[0].title == "Alpha One"
    assert posts[0].raw_content == "First useful excerpt."
    assert posts[0].published_at == datetime(2026, 4, 26, 10, 0)
    assert source is not None
    assert source.last_success_at == datetime(2026, 4, 26, 10, 30)
    assert source.last_failure_at is None
    assert source.consecutive_failures == 0
    assert source.status == "ready"
    assert source.needs_readaptation is False


def test_sync_active_sources_html_strategy_scopes_links_to_articles_and_cleans_titles() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Anthropic Engineering",
                original_url="https://anthropic.example/engineering",
                strategy_kind="html",
                strategy_config=(
                    '{"listing_url": "https://anthropic.example/engineering", '
                    '"article_selector": "article", "link_selector": "h2 a"}'
                ),
                status="needs_readaptation",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://anthropic.example/engineering": """
            <html>
              <body>
                <header>
                  <a href="/">
                    <svg><text>Anthropic</text></svg>
                    <span>Homepage chrome that must not become a post</span>
                  </a>
                </header>
                <main>
                  <article>
                    <h2>
                      <a href="/engineering/post-one">
                        <span>Post</span>
                        <em>One</em>
                      </a>
                    </h2>
                    <a href="/engineering/post-one">Read more</a>
                  </article>
                  <article>
                    <h2><a href="/engineering/post-two">Post Two</a></h2>
                  </article>
                </main>
              </body>
            </html>
            """,
            "https://anthropic.example/engineering/post-one": "<html><body><p>First paragraph.</p></body></html>",
            "https://anthropic.example/engineering/post-two": "<html><body><p>Second paragraph.</p></body></html>",
        },
        now=datetime(2026, 5, 12, 8, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post).order_by(Post.id)).all()

    assert [(post.canonical_url, post.title, post.raw_content) for post in posts] == [
        ("https://anthropic.example/engineering/post-one", "Post One", "First paragraph."),
        ("https://anthropic.example/engineering/post-two", "Post Two", "Second paragraph."),
    ]


def test_sync_active_sources_skips_inactive_sources() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Dormant",
                original_url="https://inactive.example",
                feed_url="https://inactive.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=False,
            )
        )

    processed = sync_active_sources(
        session_factory=session_factory,
        responses={"https://inactive.example/feed.xml": "<rss><channel></channel></rss>"},
        now=datetime(2026, 4, 26, 10, 30, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post)).all()
        source = session.get(Source, 1)

    assert processed == []
    assert posts == []
    assert source is not None
    assert source.last_success_at is None
    assert source.last_failure_at is None


def test_sync_active_sources_initial_feed_sync_keeps_only_recent_bounded_slice() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Alpha",
                original_url="https://alpha.example",
                feed_url="https://alpha.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://alpha.example/feed.xml": _build_feed_document(total_items=30, newest_first=False),
        },
        now=datetime(2026, 4, 30, 10, 30, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post).order_by(Post.published_at.desc(), Post.id.desc())).all()

    assert len(posts) == 25
    assert [post.canonical_url for post in posts[:3]] == [
        "https://alpha.example/posts/30",
        "https://alpha.example/posts/29",
        "https://alpha.example/posts/28",
    ]
    assert [post.canonical_url for post in posts[-3:]] == [
        "https://alpha.example/posts/8",
        "https://alpha.example/posts/7",
        "https://alpha.example/posts/6",
    ]


def test_sync_active_sources_later_sync_does_not_backfill_initial_feed_backlog() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Alpha",
                original_url="https://alpha.example",
                feed_url="https://alpha.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=True,
            )
        )

    responses = {
        "https://alpha.example/feed.xml": _build_feed_document(total_items=30),
    }

    sync_active_sources(
        session_factory=session_factory,
        responses=responses,
        now=datetime(2026, 4, 30, 10, 30, tzinfo=UTC),
    )
    sync_active_sources(
        session_factory=session_factory,
        responses=responses,
        now=datetime(2026, 4, 30, 11, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post).order_by(Post.published_at.desc(), Post.id.desc())).all()
        source = session.get(Source, 1)

    assert len(posts) == 25
    assert posts[-1].canonical_url == "https://alpha.example/posts/6"
    assert source is not None
    assert source.last_success_at == datetime(2026, 4, 30, 11, 0)


def test_sync_active_sources_triggers_readaptation_after_repeated_failures_and_keeps_old_strategy_on_failure() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Fallback",
                original_url="https://fallback.example",
                feed_url="https://fallback.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "legacy"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={},
        now=datetime(2026, 4, 26, 11, 0, tzinfo=UTC),
        failure_threshold=2,
    )
    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://fallback.example": "<html><head><title>Fallback</title></head><body></body></html>"
        },
        now=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        failure_threshold=2,
    )

    with session_scope(session_factory) as session:
        source = session.get(Source, 1)
        events = session.scalars(select(TechnicalEvent).order_by(TechnicalEvent.id)).all()

    assert source is not None
    assert source.feed_url == "https://fallback.example/feed.xml"
    assert source.strategy_kind == "feed"
    assert source.status == "needs_readaptation"
    assert source.needs_readaptation is True
    assert source.readaptation_reason == "sync failed 2 times consecutively"
    assert source.consecutive_failures == 2
    assert source.last_failure_at == datetime(2026, 4, 26, 12, 0)
    assert [event.event_code for event in events] == [
        "source.repeated_failure",
        "source.readaptation_needed",
        "source.readaptation_failed",
    ]


def test_sync_active_sources_persists_updated_strategy_when_readaptation_succeeds() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Example",
                original_url="https://example.com",
                feed_url="https://example.com/old-feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "legacy"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={},
        now=datetime(2026, 4, 26, 11, 0, tzinfo=UTC),
        failure_threshold=2,
    )
    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://example.com": """
            <html>
              <head><title>Example</title></head>
              <body>
                <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
              </body>
            </html>
            """,
            "https://example.com/feed.xml": "<rss><channel></channel></rss>",
        },
        now=datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        failure_threshold=2,
    )

    with session_scope(session_factory) as session:
        source = session.get(Source, 1)
        events = session.scalars(select(TechnicalEvent).order_by(TechnicalEvent.id)).all()

    assert source is not None
    assert source.feed_url == "https://example.com/feed.xml"
    assert source.strategy_kind == "feed"
    assert source.status == "ready"
    assert source.needs_readaptation is False
    assert source.readaptation_reason is None
    assert source.consecutive_failures == 0
    assert [event.event_code for event in events] == [
        "source.repeated_failure",
        "source.readaptation_needed",
    ]


def test_sync_active_sources_writes_post_analysis_through_analysis_flow() -> None:
    class FakeAnalysisServiceClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, str | int]] = []

        def analyze_and_persist(self, request) -> AnalysisResult:
            self.calls.append({"post_id": request.post_id, "title": request.title, "content": request.content})
            return AnalysisResult(
                summary_ru="Stubbed Russian summary",
                topics=["observability"],
                format="postmortem",
                technical_depth="deep",
                verdict="interesting",
                verdict_reason="Strong backend learning signal.",
            )

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fake_client = FakeAnalysisServiceClient()

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Alpha",
                original_url="https://alpha.example",
                feed_url="https://alpha.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://alpha.example/feed.xml": """
            <rss>
              <channel>
                <item>
                  <title>Alpha One</title>
                  <link>https://alpha.example/posts/1</link>
                  <pubDate>2026-04-26T10:00:00+00:00</pubDate>
                  <description>First useful excerpt.</description>
                </item>
              </channel>
            </rss>
            """
        },
        now=datetime(2026, 4, 26, 10, 30, tzinfo=UTC),
        analysis_service_client=fake_client,
    )

    assert fake_client.calls == [
        {
            "post_id": 1,
            "title": "Alpha One",
            "content": "First useful excerpt.",
        }
    ]


def test_sync_active_sources_fetches_live_feed_when_stub_responses_are_missing() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    requested_urls: list[str] = []

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Yegor's Blog About Computers",
                original_url="https://www.yegor256.com",
                feed_url="https://www.yegor256.com/rss.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=True,
            )
        )

    def document_loader(url: str) -> str | None:
        requested_urls.append(url)
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

    processed = sync_active_sources(
        session_factory=session_factory,
        responses={},
        document_loader=document_loader,
        now=datetime(2026, 5, 11, 8, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        posts = session.scalars(select(Post).order_by(Post.id)).all()

    assert processed == [1]
    assert [post.canonical_url for post in posts] == [
        "https://www.yegor256.com/2026/05/03/couriers-not-coders.html"
    ]
    assert requested_urls == ["https://www.yegor256.com/rss.xml"]


def test_sync_feed_strategy_stores_feed_as_date_source_in_ingest_metadata() -> None:
    import json

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Alpha",
                original_url="https://alpha.example",
                feed_url="https://alpha.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://alpha.example/feed.xml": """
            <rss>
              <channel>
                <item>
                  <title>Post with date</title>
                  <link>https://alpha.example/posts/1</link>
                  <pubDate>2026-05-11T10:00:00+00:00</pubDate>
                  <description>Content here.</description>
                </item>
              </channel>
            </rss>
            """
        },
        now=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        post = session.scalars(select(Post)).first()

    assert post is not None
    assert post.published_at == datetime(2026, 5, 11, 10, 0)  # SQLite drops tzinfo on readback
    metadata = json.loads(post.ingest_metadata)
    assert metadata["date_source"] == "feed"


def test_sync_feed_strategy_stores_none_as_date_source_when_date_absent() -> None:
    import json

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Alpha",
                original_url="https://alpha.example",
                feed_url="https://alpha.example/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "alternate_link"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://alpha.example/feed.xml": """
            <rss>
              <channel>
                <item>
                  <title>Post without date</title>
                  <link>https://alpha.example/posts/1</link>
                  <description>No date tag here.</description>
                </item>
              </channel>
            </rss>
            """
        },
        now=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        post = session.scalars(select(Post)).first()

    assert post is not None
    assert post.published_at is None
    metadata = json.loads(post.ingest_metadata)
    assert metadata["date_source"] == "none"


def test_sync_html_strategy_extracts_date_from_article_json_ld() -> None:
    import json as _json

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Spring Blog",
                original_url="https://spring.example/blog",
                strategy_kind="html",
                strategy_config='{"listing_url": "https://spring.example/blog", "link_selector": "h2 a"}',
                status="ready",
                active=True,
            )
        )

    article_html = """
    <html>
    <head>
      <script type="application/ld+json">
        {"@type": "BlogPosting", "datePublished": "2026-05-11T00:00:00Z"}
      </script>
    </head>
    <body><p>Article body text here.</p></body>
    </html>
    """
    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://spring.example/blog": """
            <html><body>
              <article>
                <h2><a href="/blog/post-one">Spring Office Hours S5E15</a></h2>
              </article>
            </body></html>
            """,
            "https://spring.example/blog/post-one": article_html,
        },
        now=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        post = session.scalars(select(Post)).first()

    assert post is not None
    assert post.published_at == datetime(2026, 5, 11, 0, 0)  # SQLite drops tzinfo on readback
    metadata = _json.loads(post.ingest_metadata)
    assert metadata["date_source"] == "json_ld"


def test_sync_html_strategy_extracts_date_from_article_og_meta() -> None:
    import json as _json

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Engineering Blog",
                original_url="https://blog.example",
                strategy_kind="html",
                strategy_config='{"listing_url": "https://blog.example", "link_selector": "h2 a"}',
                status="ready",
                active=True,
            )
        )

    article_html = """
    <html>
    <head>
      <meta property="article:published_time" content="2026-04-01T08:00:00+00:00" />
    </head>
    <body><p>Content.</p></body>
    </html>
    """
    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://blog.example": """
            <html><body>
              <article><h2><a href="/posts/alpha">Alpha Post</a></h2></article>
            </body></html>
            """,
            "https://blog.example/posts/alpha": article_html,
        },
        now=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        post = session.scalars(select(Post)).first()

    assert post is not None
    assert post.published_at == datetime(2026, 4, 1, 8, 0)  # SQLite drops tzinfo on readback
    metadata = _json.loads(post.ingest_metadata)
    assert metadata["date_source"] == "meta_og"


def test_sync_html_strategy_stores_none_date_source_when_no_date_in_article() -> None:
    import json as _json

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Minimal Blog",
                original_url="https://minimal.example",
                strategy_kind="html",
                strategy_config='{"listing_url": "https://minimal.example", "link_selector": "h2 a"}',
                status="ready",
                active=True,
            )
        )

    sync_active_sources(
        session_factory=session_factory,
        responses={
            "https://minimal.example": """
            <html><body>
              <article><h2><a href="/posts/1">No date post</a></h2></article>
            </body></html>
            """,
            "https://minimal.example/posts/1": "<html><body><p>No dates here at all.</p></body></html>",
        },
        now=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
    )

    with session_scope(session_factory) as session:
        post = session.scalars(select(Post)).first()

    assert post is not None
    assert post.published_at is None
    metadata = _json.loads(post.ingest_metadata)
    assert metadata["date_source"] == "none"


def test_refresh_post_dates_updates_posts_without_dates_from_article_pages() -> None:
    import json as _json

    from app.services.source_sync import refresh_post_dates

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Blog", original_url="https://blog.example", status="ready"))
        # Post 1: no date
        session.add(Post(
            id=1, source_id=1,
            canonical_url="https://blog.example/posts/1",
            title="Undated",
            published_at=None,
            raw_content="Content.",
            content_hash="h1",
            ingest_metadata='{"date_source":"none","source_strategy":"html","synced_at":"2026-05-11T00:00:00Z"}',
        ))
        # Post 2: already has a date — must NOT be touched
        session.add(Post(
            id=2, source_id=1,
            canonical_url="https://blog.example/posts/2",
            title="Already dated",
            published_at=datetime(2026, 4, 1, 0, 0, tzinfo=UTC),
            raw_content="Content.",
            content_hash="h2",
            ingest_metadata='{"date_source":"json_ld","source_strategy":"html","synced_at":"2026-05-11T00:00:00Z"}',
        ))

    article_html = """
    <html><head>
      <script type="application/ld+json">{"datePublished":"2026-05-11T09:00:00Z"}</script>
    </head><body><p>Body.</p></body></html>
    """

    def document_loader(url: str) -> str | None:
        return article_html if url == "https://blog.example/posts/1" else None

    with session_scope(session_factory) as session:
        result = refresh_post_dates(session=session, source_id=1, document_loader=document_loader)

    assert result == {"checked": 1, "updated": 1}

    with session_scope(session_factory) as session:
        post1 = session.get(Post, 1)
        post2 = session.get(Post, 2)

    assert post1 is not None
    assert post1.published_at is not None  # was updated
    meta1 = _json.loads(post1.ingest_metadata)
    assert meta1["date_source"] == "json_ld"
    assert "date_refreshed_at" in meta1

    assert post2 is not None
    assert post2.published_at == datetime(2026, 4, 1, 0, 0)  # unchanged — SQLite drops tzinfo
    meta2 = _json.loads(post2.ingest_metadata)
    assert meta2["date_source"] == "json_ld"  # still the original, not overwritten


def test_refresh_post_dates_returns_zero_when_no_date_found_in_article() -> None:
    from app.services.source_sync import refresh_post_dates

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Blog", original_url="https://blog.example", status="ready"))
        session.add(Post(
            id=1, source_id=1,
            canonical_url="https://blog.example/posts/1",
            title="Undated",
            published_at=None,
            raw_content="Content.",
            content_hash="h1",
            ingest_metadata='{"date_source":"none","source_strategy":"html","synced_at":"2026-05-01T00:00:00Z"}',
        ))

    def document_loader(url: str) -> str | None:
        return "<html><body><p>No date signals here.</p></body></html>"

    with session_scope(session_factory) as session:
        result = refresh_post_dates(session=session, source_id=1, document_loader=document_loader)

    assert result == {"checked": 1, "updated": 0}

    with session_scope(session_factory) as session:
        post = session.get(Post, 1)
    assert post is not None
    assert post.published_at is None  # still no date


def test_refresh_post_dates_returns_zero_when_no_undated_posts() -> None:
    from app.services.source_sync import refresh_post_dates

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Blog", original_url="https://blog.example", status="ready"))
        session.add(Post(
            id=1, source_id=1,
            canonical_url="https://blog.example/posts/1",
            title="Already dated",
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
            raw_content="Content.",
            content_hash="h1",
            ingest_metadata='{"date_source":"feed","source_strategy":"feed"}',
        ))

    calls: list[str] = []
    def document_loader(url: str) -> str | None:
        calls.append(url)
        return "<html><body></body></html>"

    with session_scope(session_factory) as session:
        result = refresh_post_dates(session=session, source_id=1, document_loader=document_loader)

    assert result == {"checked": 0, "updated": 0}
    assert calls == []  # loader never called
