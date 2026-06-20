from datetime import UTC, datetime

from app.parsing.known_sites import KnownSiteListingItem
from app.parsing.uber_engineering import parse_uber_engineering


def test_extracts_uber_cards_and_deduplicates_urls() -> None:
    document = """
        <a class="blog-card" href="/blog/engineering/one" data-date="2026-06-01">
          <h3 class="blog-card-title">Building <em>Uber</em> systems</h3>
          <p class="blog-card-excerpt"> A scalable platform. </p>
        </a>
        <a class="blog-card" href="/blog/engineering/one"><h3 class="blog-card-title">Duplicate</h3></a>
        <a class="blog-card" href="https://www.uber.com/blog/two" data-date="bad">
          <h3 class="blog-card-title">Second post</h3>
        </a>
    """

    assert parse_uber_engineering(document) == [
        KnownSiteListingItem(
            href="https://eng.uber.com/blog/engineering/one",
            title="Building Uber systems",
            published_at=datetime(2026, 6, 1, tzinfo=UTC),
            published_at_source="uber_card",
            raw_content="A scalable platform.",
        ),
        KnownSiteListingItem(
            href="https://www.uber.com/blog/two",
            title="Second post",
            published_at=None,
            published_at_source="none",
            raw_content="Second post",
        ),
    ]


def test_recovers_from_malformed_cards_and_skips_cards_without_titles() -> None:
    document = """
        <a class="blog-card" href="/broken"><h3 class="blog-card-title">Broken</span></h3>
        <a class="blog-card"><h3 class="blog-card-title">No URL</h3></a>
        <a class="blog-card" href="javascript:alert(1)"><h3 class="blog-card-title">Script</h3></a>
        <a class="blog-card" href="/missing-title">
          <p class="blog-card-excerpt">Excerpt is not a title</p>
        </a>
        <a class="blog-card" href=" /valid ">
          <h3 class="blog-card-title">Valid title</h3>
          <p class="blog-card-excerpt">Valid excerpt</p>
        </a>
    """

    assert parse_uber_engineering(document) == [
        KnownSiteListingItem(
            href="https://eng.uber.com/valid",
            title="Valid title",
            published_at=None,
            published_at_source="none",
            raw_content="Valid excerpt",
        )
    ]


def test_invalid_or_changed_layout_returns_empty_list() -> None:
    assert parse_uber_engineering("<html><body>No cards</body></html>") == []
