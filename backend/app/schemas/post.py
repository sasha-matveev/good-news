from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _extract_date_source(ingest_metadata: str | None) -> str | None:
    if not ingest_metadata:
        return None
    try:
        data = json.loads(ingest_metadata)
        return data.get("date_source") or None
    except (json.JSONDecodeError, AttributeError):
        return None


class PostResponse(BaseModel):
    id: int
    source_id: int
    source_name: str | None
    canonical_url: str
    title: str
    published_at: str | None
    published_at_source: str | None
    raw_content: str
    feedback_state: str | None
    read_later: bool
    summary_ru: str | None
    verdict: str | None
    verdict_reason: str | None
    relevance_score: int | None
    ranking_explanation: str | None

    @classmethod
    def from_row(cls, row: object) -> "PostResponse":
        return cls(
            id=row.id,
            source_id=row.source_id,
            source_name=row.source_name,
            canonical_url=row.canonical_url,
            title=row.title,
            published_at=_serialize_datetime(row.published_at),
            published_at_source=_extract_date_source(getattr(row, "ingest_metadata", None)),
            raw_content=row.raw_content,
            feedback_state=row.feedback_state,
            read_later=getattr(row, "read_later", False) or False,
            summary_ru=row.summary_ru,
            verdict=row.verdict or None,
            verdict_reason=row.verdict_reason or None,
            relevance_score=getattr(row, "relevance_score", None),
            ranking_explanation=row.ranking_explanation,
        )
