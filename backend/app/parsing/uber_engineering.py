from __future__ import annotations

from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.parsing.known_sites import KnownSiteListingItem


_LISTING_URL = "https://eng.uber.com"
_ALLOWED_HOSTS = {"eng.uber.com", "www.uber.com"}
_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


def parse_uber_engineering(document: str) -> list[KnownSiteListingItem]:
    parser = _UberCardParser()
    parser.feed(document)
    parser.close()
    return parser.items


class _UberCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._open_tags: list[str] = []
        self._card_depth: int | None = None
        self._href: str | None = None
        self._date: str | None = None
        self._title_depth: int | None = None
        self._excerpt_depth: int | None = None
        self._title_parts: list[str] = []
        self._excerpt_parts: list[str] = []
        self._seen_urls: set[str] = set()
        self.items: list[KnownSiteListingItem] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        is_card = tag == "a" and "blog-card" in classes

        if is_card and self._card_depth is not None:
            previous_depth = self._card_depth
            self._reset_card()
            del self._open_tags[previous_depth - 1 :]

        if tag not in _VOID_ELEMENTS:
            self._open_tags.append(tag)

        if self._card_depth is None:
            if is_card:
                self._card_depth = len(self._open_tags)
                self._href = _strip(attributes.get("href"))
                self._date = _strip(attributes.get("data-date"))
            return

        if tag == "br":
            if self._title_depth is not None:
                self._title_parts.append(" ")
            if self._excerpt_depth is not None:
                self._excerpt_parts.append(" ")
        elif tag == "h3" and "blog-card-title" in classes:
            self._title_depth = len(self._open_tags)
        elif tag == "p" and "blog-card-excerpt" in classes:
            self._excerpt_depth = len(self._open_tags)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._title_depth is not None:
            self._title_parts.append(data)
        if self._excerpt_depth is not None:
            self._excerpt_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        try:
            matching_index = len(self._open_tags) - 1 - self._open_tags[::-1].index(tag)
        except ValueError:
            return

        closing_depth = matching_index + 1
        if self._card_depth is not None:
            if self._title_depth is not None and closing_depth <= self._title_depth:
                self._title_depth = None
            if self._excerpt_depth is not None and closing_depth <= self._excerpt_depth:
                self._excerpt_depth = None
            if tag == "a" and self._card_depth == closing_depth:
                self._finish_card()
            elif closing_depth <= self._card_depth:
                self._reset_card()
        del self._open_tags[matching_index:]

    def _finish_card(self) -> None:
        title = _collapse(self._title_parts)
        excerpt = _collapse(self._excerpt_parts)
        canonical_url = _canonical_url(self._href)
        if title and canonical_url and canonical_url not in self._seen_urls:
            published_at = _parse_date(self._date)
            self.items.append(
                KnownSiteListingItem(
                    href=canonical_url,
                    title=title,
                    published_at=published_at,
                    published_at_source="uber_card" if published_at is not None else "none",
                    raw_content=excerpt or title,
                )
            )
            self._seen_urls.add(canonical_url)
        self._reset_card()

    def _reset_card(self) -> None:
        self._card_depth = None
        self._href = None
        self._date = None
        self._title_depth = None
        self._excerpt_depth = None
        self._title_parts.clear()
        self._excerpt_parts.clear()


def _collapse(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


def _canonical_url(href: str | None) -> str | None:
    if not href:
        return None
    candidate = urljoin(f"{_LISTING_URL}/", href)
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _ALLOWED_HOSTS:
        return None
    return candidate


def _strip(value: str | None) -> str | None:
    return value.strip() if value is not None else None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None
