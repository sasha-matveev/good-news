from __future__ import annotations

import re


def derive_html_strategy(html: str, listing_url: str) -> dict[str, str] | None:
    article_count = html.lower().count("<article")
    if article_count < 2:
        return None

    # Check for <h2><a> structure INSIDE <article> elements only.
    # A global <h2> count is unreliable because page headers/nav often contain h2 tags
    # that are not part of the article listing (e.g. claude.com/blog has <h2> in the page
    # header but articles use <h3> + bare <a>).
    article_bodies = re.findall(r"<article[^>]*>(.*?)</article>", html, re.DOTALL | re.IGNORECASE)
    articles_with_h2_link = sum(
        1 for body in article_bodies
        if re.search(r"<h2\b", body, re.IGNORECASE) and re.search(r"<a\s", body, re.IGNORECASE)
    )
    if articles_with_h2_link >= 2:
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
