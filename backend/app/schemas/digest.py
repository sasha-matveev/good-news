from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel


def serialize_digest_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class DigestListItemResponse(BaseModel):
    id: int
    digest_type: str
    status: str
    sent_at: str | None
    included_post_count: int

    @classmethod
    def from_row(cls, row: object) -> "DigestListItemResponse":
        return cls(
            id=row.id,
            digest_type=row.digest_type,
            status=row.status,
            sent_at=serialize_digest_datetime(row.sent_at),
            included_post_count=row.included_post_count,
        )


class DigestIncludedPostResponse(BaseModel):
    post_id: int
    title: str
    feedback_state: str | None = None


class DigestDetailResponse(BaseModel):
    id: int
    digest_type: str
    status: str
    sent_at: str | None
    title: str | None
    included_posts: list[DigestIncludedPostResponse]
    rendered_html: str | None
