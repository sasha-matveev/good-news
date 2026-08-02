from __future__ import annotations

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.source import Source
from app.services.source_readaptation import readapt_source


def test_readaptation_replaces_strategy_only_after_success() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        source = Source(
            display_name="Old Name",
            original_url="https://example.com",
            feed_url="https://example.com/old-feed.xml",
            strategy_kind="feed",
            strategy_config='{"discovery_method": "legacy"}',
            status="failing",
            needs_readaptation=False,
        )
        session.add(source)

    readapt_source(
        source_id=1,
        reason="consecutive sync failures",
        session_factory=session_factory,
        responses={
            "https://example.com": """
            <html>
              <head><title>Example</title></head>
              <body>
                <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
              </body>
            </html>
            """
        },
    )

    with session_scope(session_factory) as session:
        refreshed = session.get(Source, 1)

    assert refreshed is not None
    assert refreshed.feed_url == "https://example.com/feed.xml"
    assert refreshed.strategy_kind == "feed"
    assert refreshed.status == "ready"
    assert refreshed.needs_readaptation is False
    assert refreshed.readaptation_reason is None


def test_readaptation_keeps_existing_strategy_on_failure() -> None:
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
            )
        )

    readapt_source(
        source_id=1,
        reason="feed returned errors",
        session_factory=session_factory,
        responses={
            "https://fallback.example": "<html><head><title>Fallback</title></head><body></body></html>"
        },
    )

    with session_scope(session_factory) as session:
        source = session.get(Source, 1)

    assert source is not None
    assert source.feed_url == "https://fallback.example/feed.xml"
    assert source.strategy_kind == "feed"
    assert source.needs_readaptation is True
    assert source.readaptation_reason == "feed returned errors"
    assert source.status == "needs_readaptation"


def test_readaptation_uses_medium_feed_override_for_netflix_tech_blog_custom_domain() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="Old Netflix TechBlog",
                original_url="https://netflixtechblog.com",
                feed_url="https://netflixtechblog.com/feed.xml",
                strategy_kind="feed",
                strategy_config='{"discovery_method": "legacy"}',
                status="failing",
                needs_readaptation=True,
                readaptation_reason="origin certificate verification failed",
            )
        )

    readapt_source(
        source_id=1,
        reason="origin certificate verification failed",
        session_factory=session_factory,
        responses={},
    )

    with session_scope(session_factory) as session:
        source = session.get(Source, 1)

    assert source is not None
    assert source.display_name == "Netflix TechBlog"
    assert source.original_url == "https://netflixtechblog.com"
    assert source.feed_url == "https://netflixtechblog.medium.com/feed"
    assert source.strategy_kind == "feed"
    assert source.strategy_config == (
        '{"discovery_method": "source_override:netflix_medium_feed", '
        '"source_origin": "https://netflixtechblog.medium.com"}'
    )
    assert source.status == "ready"
    assert source.needs_readaptation is False
    assert source.readaptation_reason is None
