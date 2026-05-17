from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.source import Source
from app.parsing.discovery import DocumentLoader, normalize_source_url
from app.services.source_onboarding import onboard_source

LogCallback = Callable[[str], None] | None


@dataclass(frozen=True)
class SourceOnboardingCommand:
    url: str


class DuplicateSourceError(RuntimeError):
    def __init__(self, normalized_url: str) -> None:
        super().__init__(f"Source already exists for normalized URL {normalized_url}")
        self.normalized_url = normalized_url


def accept_source_onboarding_command(
    *,
    session: Session,
    command: SourceOnboardingCommand,
    responses: dict[str, str],
    document_loader: DocumentLoader | None = None,
    log_cb: LogCallback = None,
) -> Source:
    """Explicit in-process content-api -> ingestion boundary for source onboarding."""

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    normalized_url = normalize_source_url(command.url)
    log("Checking for duplicate source...")
    existing_source = session.scalar(select(Source).where(Source.original_url == normalized_url))
    if existing_source is not None:
        raise DuplicateSourceError(normalized_url)

    log("Creating source record (status: discovering)...")
    source = Source(original_url=normalized_url, status="discovering")
    session.add(source)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateSourceError(normalized_url) from exc

    onboard_source(
        source,
        session=session,
        responses=responses,
        document_loader=document_loader,
        log_cb=log_cb,
    )
    session.flush()
    return source
