from __future__ import annotations

from datetime import UTC, datetime

from app.services.analysis import StoredPostAnalysis
from app.services.ranking import RankablePostProjection, RankedPost, rank_post_projections, rank_posts


def test_rank_posts_prefers_explicit_feedback_then_affinity_then_recency() -> None:
    ranked = rank_posts(
        posts=[
            RankedPost(
                post_id=1,
                title="Kubernetes guide",
                source_name="Alpha",
                published_epoch=10,
                feedback_state=None,
                topics=["kubernetes"],
                format="guide",
                practical_engineering_score=1.0,
                technical_depth_score=0.8,
            ),
            RankedPost(
                post_id=2,
                title="Observability incident write-up",
                source_name="Beta",
                published_epoch=7,
                feedback_state="want_to_read",
                topics=["observability"],
                format="postmortem",
                practical_engineering_score=0.9,
                technical_depth_score=0.9,
            ),
            RankedPost(
                post_id=3,
                title="Frontend trends",
                source_name="Gamma",
                published_epoch=20,
                feedback_state=None,
                topics=["frontend"],
                format="opinion",
                practical_engineering_score=0.2,
                technical_depth_score=0.2,
            ),
        ],
        source_affinity={"Alpha": 0.4},
        topic_affinity={"kubernetes": 0.3, "observability": 0.6},
        format_affinity={"guide": 0.2, "postmortem": 0.1},
    )

    assert [entry.post_id for entry in ranked] == [2, 1, 3]
    assert ranked[0].score > ranked[1].score > ranked[2].score
    assert "feedback=want_to_read" in ranked[0].explanation
    assert "source_affinity=0.4" in ranked[1].explanation
    assert "topic_affinity=0.6" in ranked[0].explanation


def test_rank_post_projections_want_to_read_builds_source_affinity() -> None:
    """GOO-51: want_to_read feedback should boost source affinity for subsequent posts."""
    ranked = rank_post_projections(
        [
            RankablePostProjection(
                post_id=1,
                title="First post with want_to_read",
                source_name="Alpha",
                canonical_url="https://alpha.example/1",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="content 1",
                feedback_state="want_to_read",
                analysis=StoredPostAnalysis(
                    summary_ru="s1",
                    topics=["devops"],
                    format="guide",
                    technical_depth="medium",
                    verdict="interesting",
                    verdict_reason="r1",
                ),
            ),
            RankablePostProjection(
                post_id=2,
                title="Second post from same source, no feedback",
                source_name="Alpha",
                canonical_url="https://alpha.example/2",
                published_at=datetime(2026, 4, 19, 9, 0, tzinfo=UTC),
                raw_content="content 2",
                feedback_state=None,
                analysis=StoredPostAnalysis(
                    summary_ru="s2",
                    topics=["other"],
                    format="news",
                    technical_depth="shallow",
                    verdict="not_interesting",
                    verdict_reason="r2",
                ),
            ),
        ]
    )

    # Find post 2's ranking result
    post2_result = next(r for r in ranked if r.post_id == 2)
    # Source affinity from want_to_read on post 1 should boost post 2
    assert "source_affinity=0.4" in post2_result.explanation


def test_rank_post_projections_centralizes_feed_and_digest_ranking_inputs() -> None:
    ranked = rank_post_projections(
        [
            RankablePostProjection(
                post_id=1,
                title="Alpha deep dive",
                source_name="Alpha",
                canonical_url="https://alpha.example/1",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="content 1",
                feedback_state="interesting",
                analysis=StoredPostAnalysis(
                    summary_ru="s1",
                    topics=["observability"],
                    format="postmortem",
                    technical_depth="deep",
                    verdict="interesting",
                    verdict_reason="r1",
                ),
            ),
            RankablePostProjection(
                post_id=2,
                title="Beta short note",
                source_name="Beta",
                canonical_url="https://beta.example/2",
                published_at=datetime(2026, 4, 19, 9, 0, tzinfo=UTC),
                raw_content="content 2",
                feedback_state=None,
                analysis=StoredPostAnalysis(
                    summary_ru="s2",
                    topics=["frontend"],
                    format="news",
                    technical_depth="medium",
                    verdict="skip",
                    verdict_reason="r2",
                ),
            ),
        ]
    )

    assert [entry.post_id for entry in ranked] == [1, 2]
    assert "feedback=interesting" in ranked[0].explanation
    assert "topic_affinity=0.3" in ranked[0].explanation
