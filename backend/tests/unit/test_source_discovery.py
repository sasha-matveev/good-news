from __future__ import annotations

from app.parsing.discovery import discover_source_strategy


def test_discovery_finds_feed_from_alternate_link() -> None:
    source = discover_source_strategy(
        "example.com/blog",
        responses={
            "https://example.com/blog": """
            <html>
              <head>
                <title>Example Engineering</title>
                <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="RSS">
              </head>
            </html>
            """,
        },
    )

    assert source.normalized_url == "https://example.com/blog"
    assert source.feed_url == "https://example.com/feed.xml"
    assert source.strategy_kind == "feed"
    assert source.display_name == "Example Engineering"


def test_discovery_uses_common_feed_paths_when_homepage_has_no_links() -> None:
    source = discover_source_strategy(
        "https://signals.example",
        responses={
            "https://signals.example": "<html><head><title>Signals</title></head><body></body></html>",
            "https://signals.example/feed": """
            <?xml version="1.0" encoding="utf-8"?>
            <rss version="2.0"><channel><title>Signals Feed</title></channel></rss>
            """,
        },
    )

    assert source.feed_url == "https://signals.example/feed"
    assert source.strategy_kind == "feed"
    assert source.strategy_config == {"discovery_method": "common_feed_path"}


def test_discovery_uses_path_scoped_common_feed_paths_when_submitted_url_has_section_path() -> None:
    source = discover_source_strategy(
        "https://spring.example/blog",
        responses={
            "https://spring.example/blog": "<html><head><title>Spring Blog</title></head><body></body></html>",
            "https://spring.example/blog/feed": """
            <?xml version="1.0" encoding="utf-8"?>
            <rss version="2.0"><channel><title>Spring Blog Feed</title></channel></rss>
            """,
        },
    )

    assert source.normalized_url == "https://spring.example/blog"
    assert source.feed_url == "https://spring.example/blog/feed"
    assert source.strategy_kind == "feed"
    assert source.strategy_config == {"discovery_method": "common_feed_path"}


def test_discovery_falls_back_to_repeatable_html_strategy() -> None:
    source = discover_source_strategy(
        "https://journal.example",
        responses={
            "https://journal.example": """
            <html>
              <head><title>Field Notes</title></head>
              <body>
                <main>
                  <article>
                    <h2><a href="/posts/one">One</a></h2>
                    <p>Summary one</p>
                  </article>
                  <article>
                    <h2><a href="/posts/two">Two</a></h2>
                    <p>Summary two</p>
                  </article>
                </main>
              </body>
            </html>
            """,
        },
    )

    assert source.feed_url is None
    assert source.strategy_kind == "html"
    assert source.strategy_config == {
        "article_selector": "article",
        "link_selector": "h2 a",
        "listing_url": "https://journal.example",
    }


def test_discovery_uses_engine_hints_for_substack_feeds() -> None:
    source = discover_source_strategy(
        "notes.example",
        responses={
            "https://notes.example": """
            <html>
              <head>
                <title>Build Notes</title>
                <meta name="generator" content="Substack">
              </head>
              <body></body>
            </html>
            """,
            "https://notes.example/feed": """
            <?xml version="1.0" encoding="utf-8"?>
            <rss version="2.0"><channel><title>Build Notes</title></channel></rss>
            """,
        },
    )

    assert source.feed_url == "https://notes.example/feed"
    assert source.strategy_config == {"discovery_method": "engine_hint:substack"}


def test_discovery_fetches_live_homepage_and_feed_when_stub_responses_are_missing() -> None:
    requested_urls: list[str] = []

    def document_loader(url: str) -> str | None:
        requested_urls.append(url)
        if url == "https://www.yegor256.com":
            return """
            <html>
              <head>
                <title>Yegor's Blog About Computers</title>
                <link
                  rel="alternate"
                  type="application/rss+xml"
                  title="RSS for yegor256.com"
                  href="https://www.yegor256.com/rss.xml"
                >
              </head>
            </html>
            """
        if url == "https://www.yegor256.com/rss.xml":
            return """
            <rss version="2.0">
              <channel>
                <title>Yegor's Blog About Computers</title>
              </channel>
            </rss>
            """
        return None

    source = discover_source_strategy(
        "https://www.yegor256.com/",
        responses={},
        document_loader=document_loader,
    )

    assert source.normalized_url == "https://www.yegor256.com"
    assert source.display_name == "Yegor's Blog About Computers"
    assert source.feed_url == "https://www.yegor256.com/rss.xml"
    assert source.strategy_kind == "feed"
    assert source.strategy_config == {"discovery_method": "alternate_link"}
    assert requested_urls == [
        "https://www.yegor256.com",
        "https://www.yegor256.com/rss.xml",
    ]


def test_discovery_uses_medium_feed_override_for_netflix_tech_blog_custom_domain() -> None:
    source = discover_source_strategy(
        "https://netflixtechblog.com/",
        responses={},
    )

    assert source.normalized_url == "https://netflixtechblog.com"
    assert source.display_name == "Netflix TechBlog"
    assert source.feed_url == "https://netflixtechblog.medium.com/feed"
    assert source.strategy_kind == "feed"
    assert source.strategy_config == {
        "discovery_method": "source_override:netflix_medium_feed",
        "source_origin": "https://netflixtechblog.medium.com",
    }


def test_discovery_uses_known_site_strategy_for_claude_blog() -> None:
    source = discover_source_strategy("https://claude.com/blog", responses={})

    assert source.normalized_url == "https://claude.com/blog"
    assert source.display_name == "Claude Blog"
    assert source.feed_url is None
    assert source.strategy_kind == "known_site"
    assert source.strategy_config == {
        "discovery_method": "known_site:claude_blog",
        "parser_id": "claude_blog",
        "listing_url": "https://claude.com/blog",
    }


def test_discovery_uses_known_site_strategy_for_anthropic_engineering() -> None:
    source = discover_source_strategy("https://www.anthropic.com/engineering", responses={})

    assert source.normalized_url == "https://www.anthropic.com/engineering"
    assert source.display_name == "Anthropic Engineering"
    assert source.feed_url is None
    assert source.strategy_kind == "known_site"
    assert source.strategy_config == {
        "discovery_method": "known_site:anthropic_engineering",
        "parser_id": "anthropic_engineering",
        "listing_url": "https://www.anthropic.com/engineering",
    }
