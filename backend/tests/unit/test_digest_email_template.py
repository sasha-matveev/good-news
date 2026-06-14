from __future__ import annotations

from app.services.digest_service import DigestEmailPost, render_daily_digest_email


def test_daily_digest_template_includes_feedback_links_and_exact_remainder_line() -> None:
    html = render_daily_digest_email(
        digest_title="Good News for 2026-04-26",
        posts=[
            DigestEmailPost(
                post_id=1,
                title="Incident analysis",
                source_name="Alpha",
                canonical_url="https://alpha.example/posts/1",
                summary_ru="Русское summary.",
                verdict="interesting",
                verdict_reason="Dense practical details.",
                relevance_score=8,
            )
        ],
        more_count=3,
        feedback_base_url="https://api.good-news.example/api/feedback",
        digest_id=21,
    )

    assert "Incident analysis" in html
    assert "Alpha" in html
    assert "Русское summary." in html
    assert "interesting" in html
    assert "Dense practical details." in html
    # The same stored AI score that the feed shows is rendered in the digest.
    assert "Match: 8/10" in html
    assert "3 more posts in the collection" in html
    assert 'href="https://api.good-news.example/api/feedback/1/interesting?digest_id=21"' in html
    assert 'href="https://api.good-news.example/api/feedback/1/not_interesting?digest_id=21"' in html
    assert 'href="https://api.good-news.example/api/feedback/1/want_to_read?digest_id=21"' in html
