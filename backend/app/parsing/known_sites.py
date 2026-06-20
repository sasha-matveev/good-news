from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse


@dataclass(frozen=True)
class KnownSiteDefinition:
    parser_id: str
    normalized_url: str
    display_name: str
    article_path_prefixes: tuple[str, ...]
    excluded_path_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnownSiteListingItem:
    href: str
    title: str
    published_at: datetime | None
    published_at_source: str
    raw_content: str | None = None


KNOWN_SITE_DEFINITIONS = {
    "https://claude.com/blog": KnownSiteDefinition(
        parser_id="claude_blog",
        normalized_url="https://claude.com/blog",
        display_name="Claude Blog",
        article_path_prefixes=("/blog/",),
        excluded_path_prefixes=("/blog/category/",),
    ),
    "https://www.anthropic.com/engineering": KnownSiteDefinition(
        parser_id="anthropic_engineering",
        normalized_url="https://www.anthropic.com/engineering",
        display_name="Anthropic Engineering",
        article_path_prefixes=("/engineering/",),
    ),
    "https://eng.uber.com": KnownSiteDefinition(
        parser_id="uber_engineering",
        normalized_url="https://eng.uber.com",
        display_name="Uber Engineering",
        article_path_prefixes=("/",),
    ),
}

_KNOWN_SITE_BY_PARSER_ID = {
    definition.parser_id: definition
    for definition in KNOWN_SITE_DEFINITIONS.values()
}

_DATE_TEXT_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|June|Jul|July|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)
_ISO_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]")


def known_site_for_url(normalized_url: str) -> KnownSiteDefinition | None:
    return KNOWN_SITE_DEFINITIONS.get(normalized_url)


def known_site_for_parser_id(parser_id: str) -> KnownSiteDefinition | None:
    return _KNOWN_SITE_BY_PARSER_ID.get(parser_id)


def parse_known_site_listing(
    parser_id: str,
    document: str,
) -> list[KnownSiteListingItem]:
    if parser_id == "uber_engineering":
        from app.parsing.uber_engineering import parse_uber_engineering

        return parse_uber_engineering(document)

    definition = known_site_for_parser_id(parser_id)
    if definition is None:
        return []

    parser = _KnownSiteListingParser(definition=definition)
    parser.feed(document)
    return parser.items()


@dataclass
class _Card:
    tag: str
    depth: int
    href: str | None
    standalone_anchor: bool
    heading_chunks: list[str]
    text_chunks: list[str]
    datetime_value: str | None


class _KnownSiteListingParser(HTMLParser):
    def __init__(self, *, definition: KnownSiteDefinition) -> None:
        super().__init__()
        self._definition = definition
        self._card_stack: list[_Card] = []
        self._active_href_stack: list[str | None] = []
        self._heading_depth = 0
        self._time_depth = 0
        self._items: list[KnownSiteListingItem] = []
        self._seen_hrefs: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        attributes = {key.lower(): value or "" for key, value in attrs}
        for card in self._card_stack:
            card.depth += 1

        href = None
        if normalized_tag == "a":
            href = self._allowed_href(attributes.get("href", ""))
            self._active_href_stack.append(href)
            if href and self._card_stack:
                self._card_stack[-1].href = self._card_stack[-1].href or href

        if href and not self._card_stack:
            self._card_stack.append(
                _Card(
                    tag=normalized_tag,
                    depth=1,
                    href=href,
                    standalone_anchor=True,
                    heading_chunks=[],
                    text_chunks=[],
                    datetime_value=None,
                )
            )
        elif self._starts_card(normalized_tag, attributes):
            self._card_stack.append(
                _Card(
                    tag=normalized_tag,
                    depth=1,
                    href=self._current_active_href(),
                    standalone_anchor=False,
                    heading_chunks=[],
                    text_chunks=[],
                    datetime_value=None,
                )
            )

        if normalized_tag in {"h1", "h2", "h3", "h4"} and self._card_stack:
            self._heading_depth += 1

        if normalized_tag == "time" and self._card_stack:
            self._time_depth += 1
            datetime_value = attributes.get("datetime", "").strip()
            if datetime_value:
                self._card_stack[-1].datetime_value = datetime_value

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()

        if normalized_tag in {"h1", "h2", "h3", "h4"} and self._heading_depth > 0:
            self._heading_depth -= 1

        if normalized_tag == "time" and self._time_depth > 0:
            self._time_depth -= 1

        for card in self._card_stack:
            card.depth -= 1

        while self._card_stack and self._card_stack[-1].depth <= 0:
            self._append_card_item(self._card_stack.pop())

        if normalized_tag == "a" and self._active_href_stack:
            self._active_href_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._card_stack or not data.strip():
            return

        text = _collapse_whitespace(unescape(data))
        if not text:
            return

        card = self._card_stack[-1]
        card.text_chunks.append(text)
        if self._heading_depth > 0:
            card.heading_chunks.append(text)
        elif self._time_depth > 0 and card.datetime_value is None:
            card.datetime_value = text

    def items(self) -> list[KnownSiteListingItem]:
        while self._card_stack:
            self._append_card_item(self._card_stack.pop())
        return self._items

    def _starts_card(self, tag: str, attributes: dict[str, str]) -> bool:
        if tag == "article":
            return True
        if attributes.get("role", "").lower() == "listitem":
            return True

        class_name = attributes.get("class", "").lower()
        return (
            "w-dyn-item" in class_name
            or "blog_list_item" in class_name
            or "cms_blog_list_item" in class_name
            or "__article" in class_name
        )

    def _current_active_href(self) -> str | None:
        for href in reversed(self._active_href_stack):
            if href:
                return href
        return None

    def _allowed_href(self, raw_href: str) -> str | None:
        href = raw_href.strip()
        if not href:
            return None

        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc.lower() != urlparse(self._definition.normalized_url).netloc.lower():
            return None

        path = parsed.path if parsed.scheme else href.split("?", 1)[0].split("#", 1)[0]
        if any(path.startswith(prefix) for prefix in self._definition.excluded_path_prefixes):
            return None
        if any(path.startswith(prefix) for prefix in self._definition.article_path_prefixes):
            return href
        return None

    def _append_card_item(self, card: _Card) -> None:
        if not card.href or card.href in self._seen_hrefs:
            return

        published_at, date_source = _parse_listing_date(card)
        if card.standalone_anchor and published_at is None:
            return

        title = _collapse_whitespace(" ".join(_dedupe_chunks(card.heading_chunks)))
        if not title:
            title = _title_from_card_text(card.text_chunks, card.datetime_value)
        if not title:
            return

        self._items.append(
            KnownSiteListingItem(
                href=card.href,
                title=title,
                published_at=published_at,
                published_at_source=date_source,
            )
        )
        self._seen_hrefs.add(card.href)


def _title_from_card_text(text_chunks: list[str], datetime_value: str | None) -> str:
    title_chunks = []
    for chunk in text_chunks:
        if datetime_value and chunk == datetime_value:
            continue
        if _DATE_TEXT_RE.search(chunk):
            continue
        if chunk.lower() in {"read more", "featured"}:
            continue
        title_chunks.append(chunk)
    return _collapse_whitespace(" ".join(_dedupe_chunks(title_chunks)))


def _dedupe_chunks(chunks: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for chunk in chunks:
        normalized = chunk.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(chunk)
    return deduped


def _parse_listing_date(card: _Card) -> tuple[datetime | None, str]:
    candidates = []
    if card.datetime_value:
        candidates.append(card.datetime_value)
    candidates.extend(match.group(0) for text in card.text_chunks for match in _DATE_TEXT_RE.finditer(text))

    for candidate in candidates:
        parsed = _parse_datetime(candidate)
        if parsed is not None:
            return parsed, "known_site_listing"
    return None, "none"


def _parse_datetime(raw_value: str | None) -> datetime | None:
    if raw_value is None:
        return None
    normalized_raw_value = raw_value.strip()
    try:
        if _ISO_DATETIME_PREFIX_RE.match(normalized_raw_value):
            parsed = datetime.fromisoformat(normalized_raw_value.replace("Z", "+00:00"))
        elif _ISO_DATE_ONLY_RE.match(normalized_raw_value):
            parsed = datetime.fromisoformat(normalized_raw_value)
        else:
            parsed = parsedate_to_datetime(normalized_raw_value)
    except (TypeError, ValueError):
        return _parse_human_date(normalized_raw_value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_human_date(raw_value: str) -> datetime | None:
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%b. %d, %Y"):
        try:
            return datetime.strptime(raw_value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())
