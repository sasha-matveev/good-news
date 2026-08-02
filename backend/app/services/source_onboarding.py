from __future__ import annotations

import json
from typing import Callable
from app.parsing.discovery import DocumentLoader

from sqlalchemy.orm import Session

from app.models.source import Source
from app.parsing.discovery import DiscoveryError, DiscoveredSource, discover_source_strategy

LogCallback = Callable[[str], None] | None


def onboard_source(
    source: Source,
    session: Session,
    responses: dict[str, str],
    document_loader: DocumentLoader | None = None,
    log_cb: LogCallback = None,
) -> Source:
    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    log(f"Starting discovery for: {source.original_url}")
    try:
        discovered = discover_source_strategy(
            source.original_url,
            responses,
            document_loader=document_loader,
            log_cb=log_cb,
        )
    except DiscoveryError as exc:
        log(f"Discovery failed: {exc}")
        source.status = "failed"
        source.needs_readaptation = True
        source.readaptation_reason = str(exc)
        return source

    apply_discovery_result(source, discovered)
    if discovered.strategy_kind == "html":
        log("Strategy: html (no RSS/Atom feed — HTML fallback, needs monitoring)")
        source.status = "needs_readaptation"
        source.needs_readaptation = True
        source.readaptation_reason = "No usable feed discovered; HTML fallback requires monitoring."
    else:
        if discovered.strategy_kind == "known_site":
            log(f"Strategy: known_site — parser: {discovered.strategy_config.get('parser_id')}")
        else:
            log(f"Strategy: {discovered.strategy_kind} — feed: {discovered.feed_url}")
        source.status = "ready"
        source.needs_readaptation = False
        source.readaptation_reason = None
    log(f"Done — display_name={source.display_name!r}, status={source.status}")
    return source


def apply_discovery_result(source: Source, discovered: DiscoveredSource) -> None:
    source.display_name = discovered.display_name
    source.original_url = discovered.normalized_url
    source.feed_url = discovered.feed_url
    source.strategy_kind = discovered.strategy_kind
    source.strategy_config = json.dumps(discovered.strategy_config, sort_keys=True)
