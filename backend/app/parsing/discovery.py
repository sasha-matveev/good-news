from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from app.parsing.html_strategy import derive_html_strategy

COMMON_FEED_PATHS = ("/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml")
FEED_TYPES = {"application/rss+xml", "application/atom+xml", "application/xml", "text/xml"}
ENGINE_HINTS = {
    "substack": ("/feed",),
    "ghost": ("/rss/",),
    "wordpress": ("/feed",),
}
SOURCE_FEED_OVERRIDES = {
    "netflixtechblog.com": {
        "display_name": "Netflix TechBlog",
        "feed_url": "https://netflixtechblog.medium.com/feed",
        "strategy_config": {
            "discovery_method": "source_override:netflix_medium_feed",
            "source_origin": "https://netflixtechblog.medium.com",
        },
    },
    "www.netflixtechblog.com": {
        "display_name": "Netflix TechBlog",
        "feed_url": "https://netflixtechblog.medium.com/feed",
        "strategy_config": {
            "discovery_method": "source_override:netflix_medium_feed",
            "source_origin": "https://netflixtechblog.medium.com",
        },
    },
}


class DiscoveryError(RuntimeError):
    """Raised when no durable source strategy can be derived."""


@dataclass(frozen=True)
class DiscoveredSource:
    normalized_url: str
    display_name: str | None
    feed_url: str | None
    strategy_kind: str
    strategy_config: dict[str, str]


DocumentLoader = Callable[[str], str | None]


class _HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self._in_title = False
        self.links: list[dict[str, str]] = []
        self.meta_generators: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        normalized_tag = tag.lower()
        if normalized_tag == "title":
            self._in_title = True
            return
        if normalized_tag == "link":
            self.links.append(attributes)
            return
        if normalized_tag == "meta" and attributes.get("name", "").lower() == "generator":
            content = attributes.get("content", "").strip().lower()
            if content:
                self.meta_generators.append(content)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title = data.strip()


def normalize_source_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    path = parsed.path.rstrip("/")
    normalized = parsed._replace(scheme=parsed.scheme or "https", path=path, params="", query="", fragment="")
    return normalized.geturl()


def discover_source_strategy(
    raw_url: str,
    responses: dict[str, str],
    document_loader: DocumentLoader | None = None,
) -> DiscoveredSource:
    normalized_url = normalize_source_url(raw_url)
    override = _discover_source_feed_override(normalized_url)
    if override is not None:
        return override

    homepage = _load_document(normalized_url, responses, document_loader)
    if homepage is None:
        raise DiscoveryError(f"No response stub for {normalized_url}")

    parser = _HeadParser()
    parser.feed(homepage)
    display_name = parser.title

    alternate_feed = _discover_alternate_feed(parser, normalized_url, responses, document_loader)
    if alternate_feed is not None:
        return DiscoveredSource(
            normalized_url=normalized_url,
            display_name=display_name,
            feed_url=alternate_feed,
            strategy_kind="feed",
            strategy_config={"discovery_method": "alternate_link"},
        )

    engine_feed = _discover_engine_hint_feed(parser, normalized_url, responses, document_loader)
    if engine_feed is not None:
        return DiscoveredSource(
            normalized_url=normalized_url,
            display_name=display_name,
            feed_url=engine_feed[0],
            strategy_kind="feed",
            strategy_config={"discovery_method": engine_feed[1]},
        )

    common_feed = _discover_common_feed(normalized_url, responses, document_loader)
    if common_feed is not None:
        return DiscoveredSource(
            normalized_url=normalized_url,
            display_name=display_name,
            feed_url=common_feed,
            strategy_kind="feed",
            strategy_config={"discovery_method": "common_feed_path"},
        )

    html_strategy = derive_html_strategy(homepage, normalized_url)
    if html_strategy is not None:
        return DiscoveredSource(
            normalized_url=normalized_url,
            display_name=display_name,
            feed_url=None,
            strategy_kind="html",
            strategy_config=html_strategy,
        )

    raise DiscoveryError(f"No deterministic source strategy discovered for {normalized_url}")


def _discover_alternate_feed(
    parser: _HeadParser,
    normalized_url: str,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
) -> str | None:
    for link in parser.links:
        rel_values = {value.strip().lower() for value in link.get("rel", "").split()}
        link_type = link.get("type", "").lower()
        href = link.get("href")
        if "alternate" not in rel_values or link_type not in FEED_TYPES or not href:
            continue

        candidate = urljoin(normalized_url, href)
        document = _load_document(candidate, responses, document_loader)
        if document is None:
            if candidate not in responses and document_loader is None:
                return candidate
            continue
        if _looks_like_feed(document):
            return candidate
    return None


def _discover_engine_hint_feed(
    parser: _HeadParser,
    normalized_url: str,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
) -> tuple[str, str] | None:
    for engine, paths in ENGINE_HINTS.items():
        if not any(engine in generator for generator in parser.meta_generators):
            continue
        for path in paths:
            candidate = urljoin(_origin_url(normalized_url), path)
            if _looks_like_feed(_load_document(candidate, responses, document_loader)):
                return candidate, f"engine_hint:{engine}"
    return None


def _discover_common_feed(
    normalized_url: str,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
) -> str | None:
    for candidate in _common_feed_candidates(normalized_url):
        if _looks_like_feed(_load_document(candidate, responses, document_loader)):
            return candidate
    return None


def _common_feed_candidates(normalized_url: str) -> list[str]:
    parsed = urlparse(normalized_url)
    bases = []
    if parsed.path:
        bases.append(f"{normalized_url}/")
    bases.append(f"{_origin_url(normalized_url)}/")

    candidates: list[str] = []
    seen: set[str] = set()
    for base_url in bases:
        for path in COMMON_FEED_PATHS:
            candidate = urljoin(base_url, path.lstrip("/"))
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def _origin_url(normalized_url: str) -> str:
    parsed = urlparse(normalized_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _discover_source_feed_override(normalized_url: str) -> DiscoveredSource | None:
    parsed = urlparse(normalized_url)
    if parsed.path:
        return None

    override = SOURCE_FEED_OVERRIDES.get(parsed.netloc.lower())
    if override is None:
        return None

    return DiscoveredSource(
        normalized_url=normalized_url,
        display_name=override["display_name"],
        feed_url=override["feed_url"],
        strategy_kind="feed",
        strategy_config=override["strategy_config"],
    )


def _looks_like_feed(document: str | None) -> bool:
    if not document:
        return False
    try:
        root = ElementTree.fromstring(document.strip())
    except ElementTree.ParseError:
        return False

    tag = root.tag.lower()
    return tag.endswith("rss") or tag.endswith("feed") or tag.endswith("rdf")


def _load_document(
    url: str,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
) -> str | None:
    if url in responses:
        return responses[url]
    if document_loader is None:
        return None
    return document_loader(url)
