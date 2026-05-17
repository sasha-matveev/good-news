"""Unit tests for _extract_published_at_from_html and date-source tracking in source sync."""
from __future__ import annotations

from datetime import UTC, datetime

from app.services.source_sync import _extract_published_at_from_html  # noqa: PLC2701


# ---------------------------------------------------------------------------
# _extract_published_at_from_html — JSON-LD
# ---------------------------------------------------------------------------


def test_extract_date_from_json_ld_date_published() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type": "BlogPosting", "datePublished": "2026-05-11T00:00:00+00:00"}
      </script>
    </head></html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert dt == datetime(2026, 5, 11, 0, 0, tzinfo=UTC)
    assert source == "json_ld"


def test_extract_date_from_json_ld_date_created_fallback() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type": "Article", "dateCreated": "2026-03-15T09:30:00Z"}
      </script>
    </head></html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert dt == datetime(2026, 3, 15, 9, 30, tzinfo=UTC)
    assert source == "json_ld"


def test_extract_date_from_json_ld_list_of_objects() -> None:
    """JSON-LD can be a list; first object with a date wins."""
    html = """
    <html><head>
      <script type="application/ld+json">
        [{"@type": "WebSite"}, {"@type": "BlogPosting", "datePublished": "2026-01-20"}]
      </script>
    </head></html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert dt is not None
    assert source == "json_ld"


def test_extract_date_ignores_malformed_json_ld_and_falls_through() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">{broken json</script>
      <time datetime="2026-06-01T12:00:00Z">June 1, 2026</time>
    </head></html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert dt == datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    assert source == "time_element"


# ---------------------------------------------------------------------------
# _extract_published_at_from_html — Open Graph meta tag
# ---------------------------------------------------------------------------


def test_extract_date_from_meta_og_article_published_time() -> None:
    html = """
    <html><head>
      <meta property="article:published_time" content="2026-05-11T08:00:00+00:00" />
    </head></html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert dt == datetime(2026, 5, 11, 8, 0, tzinfo=UTC)
    assert source == "meta_og"


def test_extract_date_from_meta_og_prefers_json_ld() -> None:
    """JSON-LD takes precedence over Open Graph meta."""
    html = """
    <html><head>
      <script type="application/ld+json">{"datePublished": "2026-05-11T00:00:00Z"}</script>
      <meta property="article:published_time" content="2026-01-01T00:00:00Z" />
    </head></html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert source == "json_ld"
    assert dt == datetime(2026, 5, 11, tzinfo=UTC)


# ---------------------------------------------------------------------------
# _extract_published_at_from_html — generic meta date
# ---------------------------------------------------------------------------


def test_extract_date_from_meta_name_date() -> None:
    html = '<html><head><meta name="date" content="2026-04-20" /></head></html>'
    dt, source = _extract_published_at_from_html(html)
    assert dt is not None
    assert source == "meta_date"


def test_extract_date_from_meta_name_pubdate() -> None:
    html = '<html><head><meta name="pubdate" content="2026-04-20T10:00:00Z" /></head></html>'
    dt, source = _extract_published_at_from_html(html)
    assert dt == datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    assert source == "meta_date"


# ---------------------------------------------------------------------------
# _extract_published_at_from_html — <time> element
# ---------------------------------------------------------------------------


def test_extract_date_from_time_element() -> None:
    html = """
    <html><body>
      <article>
        <time datetime="2026-05-11T09:00:00Z">May 11, 2026</time>
      </article>
    </body></html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert dt == datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
    assert source == "time_element"


def test_extract_date_from_time_element_date_only() -> None:
    html = '<html><body><time datetime="2026-05-11">May 11</time></body></html>'
    dt, source = _extract_published_at_from_html(html)
    assert dt is not None
    assert source == "time_element"


# ---------------------------------------------------------------------------
# _extract_published_at_from_html — no date found
# ---------------------------------------------------------------------------


def test_extract_date_returns_none_when_no_date_signals_present() -> None:
    html = "<html><body><p>Just some text, no date signals.</p></body></html>"
    dt, source = _extract_published_at_from_html(html)
    assert dt is None
    assert source == "none"


def test_extract_date_returns_none_for_empty_html() -> None:
    dt, source = _extract_published_at_from_html("")
    assert dt is None
    assert source == "none"


def test_extract_date_ignores_time_element_with_no_datetime_attr() -> None:
    html = "<html><body><time>May 11, 2026</time></body></html>"
    dt, source = _extract_published_at_from_html(html)
    assert dt is None
    assert source == "none"


# ---------------------------------------------------------------------------
# Spring blog representative case
# ---------------------------------------------------------------------------


def test_extract_date_from_spring_blog_style_json_ld() -> None:
    """Reproduces the Spring blog pattern the user reported as broken."""
    html = """
    <html>
    <head>
      <meta property="article:published_time" content="2026-05-11T00:00:00+00:00">
      <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "BlogPosting",
          "headline": "Spring Office Hours Podcast: S5E15",
          "datePublished": "2026-05-11",
          "author": {"@type": "Person", "name": "Dan Vega"}
        }
      </script>
    </head>
    <body><article><time datetime="2026-05-11">May 11, 2026</time></article></body>
    </html>
    """
    dt, source = _extract_published_at_from_html(html)
    assert dt is not None
    assert source == "json_ld"
    assert dt.year == 2026
    assert dt.month == 5
    assert dt.day == 11
