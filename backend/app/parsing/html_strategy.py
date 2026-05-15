from __future__ import annotations


def derive_html_strategy(html: str, listing_url: str) -> dict[str, str] | None:
    article_count = html.lower().count("<article")
    if article_count < 2:
        return None

    if html.lower().count("<h2") >= 2 and html.lower().count("<a ") >= 2:
        return {
            "article_selector": "article",
            "link_selector": "h2 a",
            "listing_url": listing_url,
        }

    if html.lower().count("<a ") >= 2:
        return {
            "article_selector": "article",
            "link_selector": "a",
            "listing_url": listing_url,
        }

    return None
