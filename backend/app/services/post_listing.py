from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.read_later import ReadLater
from app.models.source import Source
from app.schemas.post import PostResponse
from app.services.analysis import StoredPostAnalysis
from app.services.ranking import RankablePostProjection, match_sort_value, rank_post_projections


def build_post_listing_statement(
    *,
    source_id: int | None = None,
    feedback_state: str | None = None,
    now: datetime | None = None,
    window: str = "last_month",
    read_later: bool | None = None,
) -> Select[tuple[Post, str | None, str | None]]:
    statement: Select[tuple[Post, str | None, str | None]] = (
        select(
            Post.id,
            Post.source_id,
            Source.display_name.label("source_name"),
            Post.canonical_url,
            Post.title,
            Post.published_at,
            Post.raw_content,
            Feedback.state.label("feedback_state"),
            (ReadLater.id.isnot(None)).label("read_later"),
            PostAnalysis.summary_ru.label("summary_ru"),
            PostAnalysis.metadata_json.label("analysis_metadata_json"),
        )
        .join(Source, Source.id == Post.source_id)
        .outerjoin(Feedback, Feedback.post_id == Post.id)
        .outerjoin(ReadLater, ReadLater.post_id == Post.id)
        .outerjoin(PostAnalysis, PostAnalysis.post_id == Post.id)
    )

    if window != "all":
        if now is None:
            raise ValueError("now is required when window is not all")
        statement = statement.where(Post.published_at >= now - timedelta(days=30))
    if source_id is not None:
        statement = statement.where(Post.source_id == source_id)
    if feedback_state == "none":
        # "No reaction" — posts the user has never given feedback on. Because the
        # Feedback join is outer and Feedback.state is NOT NULL, a null state here
        # means no feedback row exists at all.
        statement = statement.where(Feedback.state.is_(None))
    elif feedback_state is not None:
        statement = statement.where(Feedback.state == feedback_state)
    if read_later is True:
        statement = statement.where(ReadLater.id.isnot(None))
    elif read_later is False:
        statement = statement.where(ReadLater.id.is_(None))

    return statement


def map_rows_to_post_responses(rows: Sequence[object], *, rank_results: bool) -> list[PostResponse]:
    analysis_by_post_id: dict[int, StoredPostAnalysis] = {}
    projections: list[RankablePostProjection] = []
    for row in rows:
        analysis = StoredPostAnalysis.from_persistence(
            summary_ru=row.summary_ru,
            metadata_json=row.analysis_metadata_json,
        )
        analysis_by_post_id[row.id] = analysis
        projections.append(
            RankablePostProjection(
                post_id=row.id,
                title=row.title,
                source_name=row.source_name,
                canonical_url=row.canonical_url,
                published_at=row.published_at,
                raw_content=row.raw_content,
                feedback_state=row.feedback_state,
                analysis=analysis,
            )
        )

    explanation_by_post_id: dict[int, str | None] = {}
    ordered_rows = list(rows)
    if rank_results:
        ranked_results = rank_post_projections(projections)
        score_by_post_id = {entry.post_id: entry for entry in ranked_results}
        explanation_by_post_id = {entry.post_id: entry.explanation for entry in ranked_results}

        def _match_sort_key(row: object) -> tuple[int, int, float, int]:
            relevance = analysis_by_post_id[row.id].relevance_score
            composite = score_by_post_id[row.id].score if row.id in score_by_post_id else -9999.0
            return match_sort_value(relevance, composite, row.id)

        ordered_rows = sorted(rows, key=_match_sort_key, reverse=True)

    response_rows = []
    for row in ordered_rows:
        analysis = analysis_by_post_id[row.id]
        response_rows.append(
            type(
                "PostApiRow",
                (),
                {
                    "id": row.id,
                    "source_id": row.source_id,
                    "source_name": row.source_name,
                    "canonical_url": row.canonical_url,
                    "title": row.title,
                    "published_at": row.published_at,
                    "raw_content": row.raw_content,
                    "feedback_state": row.feedback_state,
                    "read_later": bool(getattr(row, "read_later", False)),
                    "summary_ru": analysis.summary_ru,
                    "verdict": analysis.verdict,
                    "verdict_reason": analysis.verdict_reason,
                    "relevance_score": analysis.relevance_score,
                    "ranking_explanation": explanation_by_post_id.get(row.id),
                },
            )()
        )
    return [PostResponse.from_row(row) for row in response_rows]


def list_posts(
    session: Session,
    *,
    source_id: int | None = None,
    feedback_state: str | None = None,
    now: datetime | None = None,
    window: str = "last_month",
    sort: str = "match",
    limit: int | None = None,
    offset: int = 0,
    read_later: bool | None = None,
) -> list[PostResponse]:
    rows = session.execute(
        build_post_listing_statement(
            source_id=source_id,
            feedback_state=feedback_state,
            now=now,
            window=window,
            read_later=read_later,
        ).order_by(Post.published_at.desc(), Post.id.desc())
    ).all()
    rank_results = sort != "date"
    all_responses = map_rows_to_post_responses(rows, rank_results=rank_results)
    if limit is not None:
        return all_responses[offset : offset + limit]
    return all_responses[offset:] if offset else all_responses
