from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.digest import Digest
from app.models.digest_item import DigestItem
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source
from app.services.analysis import StoredPostAnalysis
from app.services.ranking import RankablePostProjection, rank_post_projections


@dataclass(frozen=True)
class DigestEmailPost:
    post_id: int
    title: str
    source_name: str | None
    canonical_url: str
    summary_ru: str | None
    verdict: str | None
    verdict_reason: str | None


@dataclass(frozen=True)
class DigestResult:
    digest_id: int
    subject: str
    html_body: str
    posts: list[DigestEmailPost]
    more_count: int


@dataclass(frozen=True)
class DigestInput:
    post_id: int
    title: str
    source_name: str | None
    canonical_url: str
    published_at: datetime | None
    feedback_state: str | None
    summary_ru: str | None
    verdict: str | None
    verdict_reason: str | None
    ranking_score: float
    ranking_explanation: str


def render_daily_digest_email(
    *,
    digest_title: str,
    posts: list[DigestEmailPost],
    more_count: int,
    feedback_base_url: str,
    digest_id: int,
) -> str:
    normalized_feedback_base_url = feedback_base_url.rstrip("/")
    parts = ["<html><body>", f"<h1>{digest_title}</h1>"]
    for post in posts:
        parts.extend(
            [
                "<article>",
                f"<h2>{post.title}</h2>",
                f"<p>Source: {post.source_name or 'Unknown'}</p>",
                f'<p><a href="{post.canonical_url}">Open original</a></p>',
                f"<p>{post.summary_ru or ''}</p>",
                f"<p>Verdict: {post.verdict or ''}</p>",
                f"<p>Reason: {post.verdict_reason or ''}</p>",
                f'<p><a href="{normalized_feedback_base_url}/{post.post_id}/interesting?digest_id={digest_id}">interesting</a></p>',
                f'<p><a href="{normalized_feedback_base_url}/{post.post_id}/not_interesting?digest_id={digest_id}">not_interesting</a></p>',
                f'<p><a href="{normalized_feedback_base_url}/{post.post_id}/want_to_read?digest_id={digest_id}">want_to_read</a></p>',
                "</article>",
            ]
        )
    if more_count > 0:
        parts.append(f"<p>...and {more_count} more post{'s' if more_count != 1 else ''} in the collection.</p>")
    parts.append("</body></html>")
    return "".join(parts)


def _build_digest_inputs(session: Session, *, published_since: datetime | None = None) -> list[DigestInput]:
    query = (
        select(
            Post.id,
            Post.title,
            Post.canonical_url,
            Post.published_at,
            Source.display_name.label("source_name"),
            Feedback.state.label("feedback_state"),
            PostAnalysis.summary_ru.label("summary_ru"),
            PostAnalysis.metadata_json.label("analysis_metadata_json"),
        )
        .join(Source, Source.id == Post.source_id)
        .outerjoin(Feedback, Feedback.post_id == Post.id)
        .outerjoin(PostAnalysis, PostAnalysis.post_id == Post.id)
    )
    if published_since is not None:
        query = query.where(Post.published_at >= published_since)
    rows = session.execute(query).all()

    analysis_by_post_id: dict[int, StoredPostAnalysis] = {}
    rows_by_post_id: dict[int, object] = {}
    projections: list[RankablePostProjection] = []
    for row in rows:
        analysis = StoredPostAnalysis.from_persistence(
            summary_ru=row.summary_ru,
            metadata_json=row.analysis_metadata_json,
        )
        analysis_by_post_id[row.id] = analysis
        rows_by_post_id[row.id] = row
        projections.append(
            RankablePostProjection(
                post_id=row.id,
                title=row.title,
                source_name=row.source_name,
                canonical_url=row.canonical_url,
                published_at=row.published_at,
                raw_content="",
                feedback_state=row.feedback_state,
                analysis=analysis,
            )
        )

    ranked = rank_post_projections(projections)
    return [
        DigestInput(
            post_id=entry.post_id,
            title=rows_by_post_id[entry.post_id].title,
            source_name=rows_by_post_id[entry.post_id].source_name,
            canonical_url=rows_by_post_id[entry.post_id].canonical_url,
            published_at=rows_by_post_id[entry.post_id].published_at,
            feedback_state=rows_by_post_id[entry.post_id].feedback_state,
            summary_ru=analysis_by_post_id[entry.post_id].summary_ru,
            verdict=analysis_by_post_id[entry.post_id].verdict,
            verdict_reason=analysis_by_post_id[entry.post_id].verdict_reason,
            ranking_score=entry.score,
            ranking_explanation=entry.explanation,
        )
        for entry in sorted(ranked, key=lambda value: (-round(value.score, 1), value.post_id))
    ]


def _generate_digest(
    *,
    session: Session,
    now: datetime,
    frontend_base_url: str,
    content_api_base_url: str,
    digest_type: str,
    title: str,
    published_since: datetime | None = None,
) -> DigestResult:
    digest_inputs = _build_digest_inputs(session, published_since=published_since)
    top_posts = []
    for digest_input in digest_inputs[:5]:
        top_posts.append(
            DigestEmailPost(
                post_id=digest_input.post_id,
                title=digest_input.title,
                source_name=digest_input.source_name,
                canonical_url=digest_input.canonical_url,
                summary_ru=digest_input.summary_ru,
                verdict=digest_input.verdict,
                verdict_reason=digest_input.verdict_reason,
            )
        )
    more_count = max(0, len(digest_inputs) - len(top_posts))
    digest = Digest(
        digest_type=digest_type,
        scheduled_for=now,
        status="generated",
        recipient_email=None,
        subject=title,
        html_body="",
        metadata_json=json.dumps({"frontend_base_url": frontend_base_url}),
    )
    session.add(digest)
    session.flush()
    html_body = render_daily_digest_email(
        digest_title=title,
        posts=top_posts,
        more_count=more_count,
        feedback_base_url=f"{content_api_base_url.rstrip('/')}/api/feedback",
        digest_id=digest.id,
    )
    digest.html_body = html_body
    for position, post in enumerate(top_posts, start=1):
        session.add(DigestItem(digest_id=digest.id, post_id=post.post_id, rank_position=position))

    return DigestResult(
        digest_id=digest.id,
        subject=title,
        html_body=html_body,
        posts=top_posts,
        more_count=more_count,
    )


def generate_daily_digest(
    *,
    session: Session,
    now: datetime,
    frontend_base_url: str,
    content_api_base_url: str,
) -> DigestResult:
    return _generate_digest(
        session=session,
        now=now,
        frontend_base_url=frontend_base_url,
        content_api_base_url=content_api_base_url,
        digest_type="daily",
        title=f"Good News digest for {now.astimezone(UTC).date().isoformat()}",
        published_since=now - timedelta(days=1),
    )


def generate_weekly_digest(
    *,
    session: Session,
    now: datetime,
    frontend_base_url: str,
    content_api_base_url: str,
) -> DigestResult:
    return _generate_digest(
        session=session,
        now=now,
        frontend_base_url=frontend_base_url,
        content_api_base_url=content_api_base_url,
        digest_type="weekly",
        title=f"Good News weekly digest for {now.astimezone(UTC).date().isoformat()}",
        published_since=now - timedelta(days=7),
    )
