from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict

from app.models.source import Source


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SourceCreateRequest(BaseModel):
    url: str


class SourceUpdateRequest(BaseModel):
    active: bool


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str | None
    original_url: str
    feed_url: str | None
    strategy_kind: str | None
    active: bool
    status: str
    post_count: int
    last_success_at: str | None
    last_failure_at: str | None
    needs_readaptation: bool
    readaptation_reason: str | None

    @classmethod
    def from_model(cls, source: Source, post_count: int = 0) -> "SourceResponse":
        return cls(
            id=source.id,
            display_name=source.display_name,
            original_url=source.original_url,
            feed_url=source.feed_url,
            strategy_kind=source.strategy_kind,
            active=source.active,
            status=source.status,
            post_count=post_count,
            last_success_at=_serialize_datetime(source.last_success_at),
            last_failure_at=_serialize_datetime(source.last_failure_at),
            needs_readaptation=source.needs_readaptation,
            readaptation_reason=source.readaptation_reason,
        )
