from __future__ import annotations

import json
from app.parsing.discovery import DocumentLoader

from sqlalchemy.orm import Session

from app.models.setting import TechnicalEvent
from app.models.source import Source
from app.parsing.discovery import DiscoveryError, DiscoveredSource, discover_source_strategy


def onboard_source(
    source: Source,
    session: Session,
    responses: dict[str, str],
    document_loader: DocumentLoader | None = None,
) -> Source:
    try:
        discovered = discover_source_strategy(
            source.original_url,
            responses,
            document_loader=document_loader,
        )
    except DiscoveryError as exc:
        source.status = "failed"
        source.needs_readaptation = True
        source.readaptation_reason = str(exc)
        session.add(
            TechnicalEvent(
                severity="warning",
                subsystem="source-onboarding",
                event_code="source.onboarding_failed",
                summary="Source onboarding failed.",
                details=str(exc),
                source_id=source.id,
            )
        )
        return source

    apply_discovery_result(source, discovered)
    if discovered.strategy_kind == "html":
        source.status = "needs_readaptation"
        source.needs_readaptation = True
        source.readaptation_reason = "No usable feed discovered; HTML fallback requires monitoring."
        session.add(
            TechnicalEvent(
                severity="warning",
                subsystem="source-onboarding",
                event_code="source.readaptation_needed",
                summary="Source onboarded with HTML fallback only.",
                details=source.readaptation_reason,
                source_id=source.id,
            )
        )
    else:
        source.status = "ready"
        source.needs_readaptation = False
        source.readaptation_reason = None
    return source


def apply_discovery_result(source: Source, discovered: DiscoveredSource) -> None:
    source.display_name = discovered.display_name
    source.original_url = discovered.normalized_url
    source.feed_url = discovered.feed_url
    source.strategy_kind = discovered.strategy_kind
    source.strategy_config = json.dumps(discovered.strategy_config, sort_keys=True)
