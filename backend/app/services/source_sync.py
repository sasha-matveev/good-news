from __future__ import annotations

import hashlib
import json
import re as _re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.models.feedback import Feedback
from app.core.observability import record_analysis_failure, record_source_sync_failure
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.read_later import ReadLater
from app.models.setting import TechnicalEvent
from app.models.source import Source
from app.parsing.discovery import DocumentLoader
from app.services.analysis import AnalysisRequest
from app.services.source_readaptation import readapt_source_model

MAX_POSTS_PER_SOURCE_SYNC = 25
_MIN_UTC_DATETIME = datetime.min.replace(tzinfo=UTC)


class SourceSyncError(RuntimeError):
    """Raised when a source cannot be synced with its stored strategy."""


@dataclass(frozen=True)
class ParsedPost:
    canonical_url: str
    title: str
    published_at: datetime | None
    raw_content: str
    # How the date was obtained: "feed" | "json_ld" | "meta_og" | "meta_date" | "time_element" | "none"
    published_at_source: str = field(default="none")


class _HtmlStripper(HTMLParser):
    """Extract plain text from an HTML fragment."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return _collapse_whitespace("".join(self._chunks))


def _strip_html(value: str) -> str:
    """Return plain text with all HTML tags and entities removed."""
    import html as _html_module
    # First unescape entities, then strip tags
    unescaped = _html_module.unescape(value)
    stripper = _HtmlStripper()
    try:
        stripper.feed(unescaped)
    except Exception:
        return _collapse_whitespace(unescaped)
    return stripper.get_text()


# Matches common RSS boilerplate appended by Medium/Ghost/WordPress:
#   "The post <title> appeared first on <Site>."
#   "This post appeared first on <Site>."
_RSS_BOILERPLATE_RE = _re.compile(
    r"\s*(The post .+? appeared first on .+?\.|This post appeared first on .+?\.)\s*$",
    _re.IGNORECASE | _re.DOTALL,
)


def _strip_rss_boilerplate(text: str) -> str:
    """Remove common RSS trailer lines like 'The post X appeared first on Y.'"""
    return _RSS_BOILERPLATE_RE.sub("", text).strip()


class _HtmlListingLinkParser(HTMLParser):
    def __init__(self, link_selector: str) -> None:
        super().__init__()
        self._link_selector = link_selector
        self._article_stack: list[bool] = []
        self._heading_depth = 0
        self._current_href: str | None = None
        self._current_text_chunks: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "article":
            self._article_stack.append(False)
            return

        if normalized_tag == "h2" and self._article_stack:
            self._heading_depth += 1
            return

        if normalized_tag != "a" or not self._article_stack or self._article_stack[-1]:
            return

        if self._link_selector == "h2 a" and self._heading_depth == 0:
            return

        attributes = {key.lower(): value or "" for key, value in attrs}
        href = attributes.get("href", "").strip()
        if not href:
            return

        self._current_href = href
        self._current_text_chunks = []

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "a" and self._current_href is not None and self._article_stack:
            title = _collapse_whitespace(" ".join(self._current_text_chunks))
            if title:
                self.links.append((self._current_href, title))
                self._article_stack[-1] = True
            self._current_href = None
            self._current_text_chunks = []
            return

        if normalized_tag == "h2" and self._heading_depth > 0:
            self._heading_depth -= 1
            return

        if normalized_tag == "article" and self._article_stack:
            self._article_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._current_href is None or not data.strip():
            return
        self._current_text_chunks.append(data)


def sync_active_sources(
    session_factory: sessionmaker[Session],
    responses: dict[str, str],
    document_loader: DocumentLoader | None = None,
    now: datetime | None = None,
    failure_threshold: int = 3,
    analysis_service_client: object | None = None,
    source_ids: list[int] | None = None,
) -> list[int]:
    sync_time = now or datetime.now(UTC)
    processed_source_ids: list[int] = []

    with session_scope(session_factory) as session:
        if source_ids is not None:
            sources = session.scalars(select(Source).where(Source.id.in_(source_ids)).order_by(Source.id)).all()
        else:
            sources = session.scalars(select(Source).where(Source.active.is_(True)).order_by(Source.id)).all()
        for source in sources:
            try:
                parsed_posts = _load_posts_for_source(source, responses, document_loader)
                candidate_posts = _select_posts_for_sync(source=source, parsed_posts=parsed_posts)
                new_posts = _persist_posts(session, source, candidate_posts, sync_time)
                if new_posts:
                    # Commit canonical post writes before cross-runtime analysis so the external owner
                    # can read the stable post identity and satisfy FK constraints on post_analysis.
                    session.commit()
                    _persist_post_analysis(
                        session=session,
                        posts=new_posts,
                        analysis_service_client=analysis_service_client,
                    )
                source.last_success_at = sync_time
                source.status = "ready"
                source.needs_readaptation = False
                source.readaptation_reason = None
                source.consecutive_failures = 0
                processed_source_ids.append(source.id)
            except SourceSyncError as exc:
                _record_sync_failure(
                    session=session,
                    source=source,
                    reason=str(exc),
                    responses=responses,
                    document_loader=document_loader,
                    now=sync_time,
                    failure_threshold=failure_threshold,
                )

    return processed_source_ids


_REFRESH_LIMIT = 60  # max posts to re-fetch per refresh call
_RELOAD_WINDOW_DAYS = 60


def refresh_post_dates(
    *,
    session: Session,
    source_id: int,
    document_loader: DocumentLoader,
    limit: int = _REFRESH_LIMIT,
) -> dict[str, int]:
    """Re-fetch article pages for posts that have no publication date and fill it in.

    Only targets posts where published_at IS NULL (i.e. date was never found),
    ordered by most-recently ingested first, capped at *limit* posts to avoid
    hammering the origin server with too many requests in one go.

    Returns {"checked": N, "updated": M} — M <= N.
    """
    posts_without_date = session.scalars(
        select(Post)
        .where(Post.source_id == source_id, Post.published_at.is_(None))
        .order_by(Post.id.desc())
        .limit(limit)
    ).all()

    checked = 0
    updated = 0

    for post in posts_without_date:
        checked += 1
        try:
            html = document_loader(post.canonical_url)
        except Exception:
            continue
        if not html:
            continue

        published_at, date_source = _extract_published_at_from_html(html)
        if published_at is None:
            continue

        post.published_at = published_at

        # Patch date_source in the existing ingest_metadata JSON
        try:
            meta: dict[str, object] = json.loads(post.ingest_metadata or "{}")
        except (json.JSONDecodeError, ValueError):
            meta = {}
        meta["date_source"] = date_source
        meta["date_refreshed_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        post.ingest_metadata = json.dumps(meta, sort_keys=True)

        updated += 1

    return {"checked": checked, "updated": updated}


def reload_recent_posts(
    *,
    session: Session,
    source_id: int,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
    analysis_service_client: object | None,
    now: datetime,
    recent_days: int = _RELOAD_WINDOW_DAYS,
) -> dict[str, int]:
    source = session.get(Source, source_id)
    if source is None:
        raise LookupError(f"Source {source_id} not found")

    cutoff = now.astimezone(UTC) - timedelta(days=recent_days)
    recent_post_ids = list(
        session.scalars(
            select(Post.id).where(
                Post.source_id == source_id,
                func.coalesce(Post.published_at, Post.created_at) >= cutoff,
            )
        ).all()
    )

    if recent_post_ids:
        session.execute(sa_delete(Feedback).where(Feedback.post_id.in_(recent_post_ids)))
        session.execute(sa_delete(ReadLater).where(ReadLater.post_id.in_(recent_post_ids)))
        session.execute(sa_delete(PostAnalysis).where(PostAnalysis.post_id.in_(recent_post_ids)))
        session.execute(sa_delete(Post).where(Post.id.in_(recent_post_ids)))

    parsed_posts = _load_posts_for_source(source, responses, document_loader)
    reloadable_posts = [
        post for post in parsed_posts
        if post.published_at is None or (_normalize_utc(post.published_at) or _MIN_UTC_DATETIME) >= cutoff
    ]
    new_posts = _persist_posts(session, source, reloadable_posts, now)

    source.last_success_at = now
    source.status = "ready"
    source.needs_readaptation = False
    source.readaptation_reason = None
    source.consecutive_failures = 0

    if new_posts:
        session.commit()
        _persist_post_analysis(
            session=session,
            posts=new_posts,
            analysis_service_client=analysis_service_client,
        )

    return {"deleted": len(recent_post_ids), "reloaded": len(new_posts)}


def _select_posts_for_sync(*, source: Source, parsed_posts: list[ParsedPost]) -> list[ParsedPost]:
    if source.strategy_kind == "feed":
        indexed_feed_candidates = list(enumerate(parsed_posts))
        last_success_at = _normalize_utc(source.last_success_at)
        if last_success_at is not None:
            indexed_feed_candidates = [
                (index, post)
                for index, post in indexed_feed_candidates
                if post.published_at is None or _normalize_utc(post.published_at) > last_success_at
            ]

        if len(indexed_feed_candidates) <= MAX_POSTS_PER_SOURCE_SYNC:
            return [post for _, post in indexed_feed_candidates]

        recent_slice = sorted(
            indexed_feed_candidates,
            key=lambda indexed_post: _normalize_utc(indexed_post[1].published_at) or _MIN_UTC_DATETIME,
            reverse=True,
        )[:MAX_POSTS_PER_SOURCE_SYNC]
        recent_slice.sort(key=lambda indexed_post: indexed_post[0])
        return [post for _, post in recent_slice]

    return parsed_posts


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _persist_posts(
    session: Session,
    source: Source,
    parsed_posts: list[ParsedPost],
    sync_time: datetime,
) -> list[Post]:
    seen_urls = {
        value
        for value in session.scalars(select(Post.canonical_url)).all()
    }
    seen_hashes = {
        value
        for value in session.scalars(select(Post.content_hash)).all()
    }
    new_posts: list[Post] = []
    for post in parsed_posts:
        if post.canonical_url in seen_urls:
            continue

        content_hash = hashlib.sha256(post.raw_content.strip().encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            continue

        stored_post = Post(
            source_id=source.id,
            canonical_url=post.canonical_url,
            title=post.title,
            published_at=post.published_at,
            raw_content=post.raw_content,
            content_hash=content_hash,
            ingest_metadata=json.dumps(
                {
                    "date_source": post.published_at_source,
                    "source_strategy": source.strategy_kind,
                    "synced_at": sync_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                },
                sort_keys=True,
            ),
        )
        session.add(stored_post)
        session.flush()
        new_posts.append(stored_post)
        seen_urls.add(post.canonical_url)
        seen_hashes.add(content_hash)
    return new_posts


def _persist_post_analysis(
    *,
    session: Session,
    posts: list[Post],
    analysis_service_client: object | None,
) -> None:
    if analysis_service_client is None:
        return

    for post in posts:
        try:
            analysis_service_client.analyze_and_persist(
                AnalysisRequest(post_id=post.id, title=post.title, content=post.raw_content),
            )
        except Exception as exc:
            record_analysis_failure(reason="write_failed")
            session.add(
                TechnicalEvent(
                    severity="warning",
                    subsystem="analysis",
                    event_code="analysis.write_failed",
                    summary="Post analysis write failed.",
                    details=str(exc),
                    source_id=post.source_id,
                )
            )


def _record_sync_failure(
    session: Session,
    source: Source,
    reason: str,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
    now: datetime,
    failure_threshold: int,
) -> None:
    source.last_failure_at = now
    source.consecutive_failures += 1
    source.status = "failing"

    if source.consecutive_failures < failure_threshold:
        return

    readaptation_reason = f"sync failed {source.consecutive_failures} times consecutively"
    session.add(
        TechnicalEvent(
            severity="warning",
            subsystem="source-sync",
            event_code="source.repeated_failure",
            summary="Source sync hit the repeated-failure threshold.",
            details=reason,
            source_id=source.id,
        )
    )
    record_source_sync_failure(event_code="source.repeated_failure")
    session.add(
        TechnicalEvent(
            severity="warning",
            subsystem="source-sync",
            event_code="source.readaptation_needed",
            summary="Source sync requested readaptation.",
            details=readaptation_reason,
            source_id=source.id,
        )
    )
    record_source_sync_failure(event_code="source.readaptation_needed")
    readapt_source_model(
        source=source,
        reason=readaptation_reason,
        session=session,
        responses=responses,
        document_loader=document_loader,
    )


def _load_posts_for_source(
    source: Source,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
) -> list[ParsedPost]:
    if source.strategy_kind == "feed":
        if not source.feed_url:
            raise SourceSyncError("Feed strategy is missing a feed URL")
        document = _load_document(source.feed_url, responses, document_loader)
        if document is None:
            raise SourceSyncError(f"No response stub for {source.feed_url}")
        return _parse_feed_document(document)

    if source.strategy_kind == "html":
        return _parse_html_listing(source, responses, document_loader)

    raise SourceSyncError(f"Unsupported source strategy {source.strategy_kind}")


class _DateMetaParser(HTMLParser):
    """Single-pass HTML parser that collects meta date attributes and <time datetime>."""

    # <meta property/name> values that carry publication date
    _DATE_PROPERTIES = frozenset(
        ["article:published_time", "article:modified_time", "og:updated_time"]
    )
    _DATE_NAMES = frozenset(
        ["date", "pubdate", "dc.date", "dc.date.issued", "published_time", "article.published"]
    )

    def __init__(self) -> None:
        super().__init__()
        self.meta_dates: list[tuple[str, str]] = []  # [(source_label, value), ...]
        self.time_datetime: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower == "meta":
            content = attr_map.get("content", "").strip()
            if not content:
                return
            prop = attr_map.get("property", "").lower()
            name = attr_map.get("name", "").lower()
            if prop in self._DATE_PROPERTIES:
                self.meta_dates.append(("meta_og", content))
            elif name in self._DATE_NAMES:
                self.meta_dates.append(("meta_date", content))

        elif tag_lower == "time" and self.time_datetime is None:
            dt_val = attr_map.get("datetime", "").strip()
            if dt_val:
                self.time_datetime = dt_val


def _extract_published_at_from_html(html: str) -> tuple[datetime | None, str]:
    """Try to extract a publication date from article HTML using multiple strategies.

    Returns (datetime_or_none, source_label) where source_label is one of:
      "json_ld", "meta_og", "meta_date", "time_element", "none"
    """
    # 1. JSON-LD structured data — most reliable
    for script_content in _re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        _re.IGNORECASE | _re.DOTALL,
    ):
        try:
            data = json.loads(script_content)
        except (json.JSONDecodeError, ValueError):
            continue
        # data may be a list of graph objects
        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            for key in ("datePublished", "dateCreated", "dateModified"):
                raw = obj.get(key)
                if raw and isinstance(raw, str):
                    parsed = _parse_datetime(raw)
                    if parsed is not None:
                        return parsed, "json_ld"

    # 2. Meta tags and <time> elements
    parser = _DateMetaParser()
    try:
        parser.feed(html)
    except Exception:
        pass

    for source_label, raw in parser.meta_dates:
        parsed = _parse_datetime(raw)
        if parsed is not None:
            return parsed, source_label

    if parser.time_datetime is not None:
        parsed = _parse_datetime(parser.time_datetime)
        if parsed is not None:
            return parsed, "time_element"

    return None, "none"


def _parse_feed_document(document: str) -> list[ParsedPost]:
    try:
        root = ElementTree.fromstring(document.strip())
    except ElementTree.ParseError as exc:
        raise SourceSyncError("Stored feed response could not be parsed") from exc

    items = list(root.findall(".//item"))
    if not items:
        items = list(root.findall(".//{*}entry"))

    parsed_posts: list[ParsedPost] = []
    for item in items:
        link = _child_text(item, "link")
        if not link:
            link_element = item.find("{*}link")
            link = link_element.attrib.get("href") if link_element is not None else None
        title = _child_text(item, "title") or "Untitled post"
        description = _child_text(item, "description") or _child_text(item, "summary") or title
        if not link:
            continue
        raw_date_str = _child_text(item, "pubDate") or _child_text(item, "published") or _child_text(item, "updated")
        published_at = _parse_datetime(raw_date_str)
        published_at_source = "feed" if published_at is not None else "none"
        parsed_posts.append(
            ParsedPost(
                canonical_url=link.strip(),
                title=_strip_html(title.strip()),
                published_at=published_at,
                raw_content=_strip_rss_boilerplate(_strip_html(description.strip())),
                published_at_source=published_at_source,
            )
        )
    return parsed_posts


def _parse_html_listing(
    source: Source,
    responses: dict[str, str],
    document_loader: DocumentLoader | None,
) -> list[ParsedPost]:
    strategy_config: dict[str, Any] = json.loads(source.strategy_config or "{}")
    listing_url = strategy_config.get("listing_url") or source.original_url
    link_selector = strategy_config.get("link_selector") or "a"
    document = _load_document(listing_url, responses, document_loader)
    if document is None:
        raise SourceSyncError(f"No response stub for {listing_url}")

    links = _extract_links(document, link_selector=link_selector)
    if not links:
        raise SourceSyncError(
            f"No links found on listing page using selector '{link_selector}'. "
            "The page structure may not match the configured strategy — "
            "delete and re-add this source to re-run discovery."
        )

    parsed_posts: list[ParsedPost] = []
    for href, title in links:
        article_url = urljoin(listing_url, href)
        article_document = _load_document(article_url, responses, document_loader) or ""
        raw_content = _extract_first_paragraph(article_document) or title
        published_at, published_at_source = _extract_published_at_from_html(article_document)
        parsed_posts.append(
            ParsedPost(
                canonical_url=article_url,
                title=title,
                published_at=published_at,
                raw_content=raw_content,
                published_at_source=published_at_source,
            )
        )
    return parsed_posts


def _extract_links(document: str, *, link_selector: str) -> list[tuple[str, str]]:
    parser = _HtmlListingLinkParser(link_selector=link_selector)
    parser.feed(document)
    return parser.links


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _extract_first_paragraph(document: str) -> str | None:
    lower_document = document.lower()
    paragraph_start = lower_document.find("<p>")
    paragraph_end = lower_document.find("</p>", paragraph_start + 3)
    if paragraph_start == -1 or paragraph_end == -1:
        return None
    raw = document[paragraph_start + 3 : paragraph_end].strip()
    return _strip_html(raw) or None


def _child_text(element: ElementTree.Element, tag_name: str) -> str | None:
    child = element.find(tag_name)
    if child is not None and child.text:
        return child.text
    namespaced = element.find(f"{{*}}{tag_name}")
    if namespaced is not None and namespaced.text:
        return namespaced.text
    return None


_ISO_DATE_ONLY_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_PREFIX_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}[T ]")


def _parse_datetime(raw_value: str | None) -> datetime | None:
    if raw_value is None:
        return None
    normalized_raw_value = raw_value.strip()
    try:
        if _ISO_DATETIME_PREFIX_RE.match(normalized_raw_value):
            # ISO 8601 with time component
            normalized = normalized_raw_value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        elif _ISO_DATE_ONLY_RE.match(normalized_raw_value):
            # Date-only ISO 8601 like "2026-05-11" — treat as midnight UTC
            parsed = datetime.fromisoformat(normalized_raw_value)
        else:
            # RFC 2822 as used in RSS <pubDate>
            parsed = parsedate_to_datetime(normalized_raw_value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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
