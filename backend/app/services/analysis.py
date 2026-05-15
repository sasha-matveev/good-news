from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post_analysis import PostAnalysis


@dataclass(frozen=True)
class AnalysisResult:
    summary_ru: str
    topics: list[str]
    format: str
    technical_depth: str
    verdict: str
    verdict_reason: str

    def as_persistence_payload(self) -> dict[str, str]:
        return {
            "summary_ru": self.summary_ru,
            "metadata_json": json.dumps(
                {
                    "topics": self.topics,
                    "format": self.format,
                    "technical_depth": self.technical_depth,
                    "verdict": self.verdict,
                    "verdict_reason": self.verdict_reason,
                },
                sort_keys=True,
            ),
        }


@dataclass(frozen=True)
class AnalysisRequest:
    post_id: int
    title: str
    content: str


@dataclass(frozen=True)
class StoredPostAnalysis:
    """Analysis-owned persistence shape for rows stored in post_analysis."""

    summary_ru: str | None
    topics: list[str]
    format: str | None
    technical_depth: str | None
    verdict: str | None
    verdict_reason: str | None

    @classmethod
    def from_persistence(
        cls,
        *,
        summary_ru: str | None,
        metadata_json: str | None,
    ) -> "StoredPostAnalysis":
        metadata = json.loads(metadata_json or "{}")
        return cls(
            summary_ru=summary_ru,
            topics=list(metadata.get("topics", [])),
            format=metadata.get("format"),
            technical_depth=metadata.get("technical_depth"),
            verdict=metadata.get("verdict"),
            verdict_reason=metadata.get("verdict_reason") or None,
        )


def analyze_request(
    request: AnalysisRequest,
    ollama_client: object,
) -> AnalysisResult:
    result = ollama_client.analyze_article(title=request.title, content=request.content)
    return AnalysisResult(
        summary_ru=result.summary_ru,
        topics=list(result.topics),
        format=result.format,
        technical_depth=result.technical_depth,
        verdict=result.verdict,
        verdict_reason=result.verdict_reason,
    )


def persist_analysis_result(
    *,
    session: Session,
    request: AnalysisRequest,
    result: AnalysisResult,
) -> PostAnalysis:
    existing = session.scalar(select(PostAnalysis).where(PostAnalysis.post_id == request.post_id))
    payload = result.as_persistence_payload()
    if existing is None:
        existing = PostAnalysis(
            post_id=request.post_id,
            summary_ru=payload["summary_ru"],
            metadata_json=payload["metadata_json"],
        )
        session.add(existing)
    else:
        existing.summary_ru = payload["summary_ru"]
        existing.metadata_json = payload["metadata_json"]
    session.flush()
    return existing


def analyze_post_payload(
    title: str,
    content: str,
    ollama_client: object,
) -> dict[str, str]:
    normalized = analyze_request(
        AnalysisRequest(post_id=0, title=title, content=content),
        ollama_client=ollama_client,
    )
    return normalized.as_persistence_payload()
