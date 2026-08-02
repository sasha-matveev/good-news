from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.models.source import Source
from app.parsing.discovery import DiscoveryError, DocumentLoader, discover_source_strategy
from app.services.source_onboarding import apply_discovery_result


def readapt_source_model(
    source: Source,
    reason: str,
    session: Session,
    responses: dict[str, str],
    document_loader: DocumentLoader | None = None,
) -> Source:
    source.needs_readaptation = True
    source.readaptation_reason = reason
    source.status = "needs_readaptation"

    try:
        discovered = discover_source_strategy(
            source.original_url,
            responses,
            document_loader=document_loader,
        )
    except DiscoveryError:
        return source

    apply_discovery_result(source, discovered)
    source.status = "ready"
    source.needs_readaptation = False
    source.readaptation_reason = None
    source.consecutive_failures = 0
    return source


def readapt_source(
    source_id: int,
    reason: str,
    session_factory: sessionmaker[Session],
    responses: dict[str, str],
    document_loader: DocumentLoader | None = None,
) -> Source:
    with session_scope(session_factory) as session:
        source = session.get(Source, source_id)
        if source is None:
            raise LookupError(f"Source {source_id} not found")
        return readapt_source_model(
            source=source,
            reason=reason,
            session=session,
            responses=responses,
            document_loader=document_loader,
        )
