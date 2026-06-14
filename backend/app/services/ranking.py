from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.analysis import StoredPostAnalysis


FEEDBACK_WEIGHTS = {
    "interesting": 4.0,
    "want_to_read": 5.0,
    "not_interesting": -4.0,
    None: 0.0,
}

DEPTH_WEIGHTS = {
    "shallow": 0.1,
    "medium": 0.35,
    "deep": 0.7,
}


@dataclass(frozen=True)
class RankedPost:
    post_id: int
    title: str
    source_name: str | None
    published_epoch: int
    feedback_state: str | None
    topics: list[str]
    format: str | None
    practical_engineering_score: float
    technical_depth_score: float


@dataclass(frozen=True)
class RankingResult:
    post_id: int
    score: float
    explanation: str


@dataclass(frozen=True)
class RankablePostProjection:
    post_id: int
    title: str
    source_name: str | None
    canonical_url: str
    published_at: datetime | None
    raw_content: str
    feedback_state: str | None
    analysis: StoredPostAnalysis


def rank_posts(
    posts: list[RankedPost],
    source_affinity: dict[str, float],
    topic_affinity: dict[str, float],
    format_affinity: dict[str, float],
) -> list[RankingResult]:
    if not posts:
        return []

    latest_epoch = max(post.published_epoch for post in posts)
    ranked: list[RankingResult] = []
    for post in posts:
        feedback_score = FEEDBACK_WEIGHTS.get(post.feedback_state, 0.0)
        source_score = source_affinity.get(post.source_name or "", 0.0)
        topic_score = max((topic_affinity.get(topic, 0.0) for topic in post.topics), default=0.0)
        format_score = format_affinity.get(post.format or "", 0.0)
        recency_score = max(0.0, (post.published_epoch / latest_epoch) * 0.3) if latest_epoch else 0.0
        total = (
            feedback_score
            + source_score
            + topic_score
            + format_score
            + post.practical_engineering_score
            + post.technical_depth_score
            + recency_score
        )
        explanation = (
            f"feedback={post.feedback_state or 'none'}; "
            f"source_affinity={source_score}; "
            f"topic_affinity={topic_score}; "
            f"format_affinity={format_score}; "
            f"practical={post.practical_engineering_score}; "
            f"depth={post.technical_depth_score}; "
            f"recency={round(recency_score, 3)}"
        )
        ranked.append(RankingResult(post_id=post.post_id, score=total, explanation=explanation))
    return sorted(ranked, key=lambda item: (item.score, item.post_id), reverse=True)


def rank_post_projections(posts: list[RankablePostProjection]) -> list[RankingResult]:
    if not posts:
        return []

    source_affinity: dict[str, float] = {}
    topic_affinity: dict[str, float] = {}
    format_affinity: dict[str, float] = {}
    rank_inputs: list[RankedPost] = []

    for post in posts:
        if post.feedback_state in {"interesting", "want_to_read"}:
            source_affinity[post.source_name or ""] = source_affinity.get(post.source_name or "", 0.0) + 0.4
            for topic in post.analysis.topics:
                topic_affinity[topic] = topic_affinity.get(topic, 0.0) + 0.3
            if post.analysis.format:
                format_affinity[post.analysis.format] = format_affinity.get(post.analysis.format, 0.0) + 0.2

        rank_inputs.append(
            RankedPost(
                post_id=post.post_id,
                title=post.title,
                source_name=post.source_name,
                published_epoch=int(post.published_at.timestamp()) if post.published_at else 0,
                feedback_state=post.feedback_state,
                topics=post.analysis.topics,
                format=post.analysis.format,
                practical_engineering_score=0.6 if post.analysis.verdict == "interesting" else 0.1,
                technical_depth_score=depth_score(post.analysis.technical_depth),
            )
        )

    return rank_posts(
        posts=rank_inputs,
        source_affinity=source_affinity,
        topic_affinity=topic_affinity,
        format_affinity=format_affinity,
    )


def depth_score(raw_depth: str | None) -> float:
    return DEPTH_WEIGHTS.get(raw_depth or "", 0.0)


def match_sort_value(
    relevance_score: int | None,
    composite_score: float,
    post_id: int,
) -> tuple[int, int, float, int]:
    """Shared feed/digest ordering key — use with ``reverse=True``.

    The post's stored, profile-aware AI relevance score is the primary signal, so
    a post is ordered the same way everywhere it appears. Posts that have been
    analyzed (score present) always rank above not-yet-analyzed ones; the
    heuristic composite then breaks ties and orders the un-analyzed tail by
    feedback + recency.
    """
    return (
        1 if relevance_score is not None else 0,
        relevance_score if relevance_score is not None else 0,
        composite_score,
        post_id,
    )
