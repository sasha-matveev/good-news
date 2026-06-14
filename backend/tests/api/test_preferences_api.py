from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.content_api_service.main import create_app
from app.models.base import Base
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.preference_profile import PreferenceProfile
from app.models.source import Source
from app.testing.schema import stamp_schema_head


def build_client() -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    app = create_app(
        session_factory=session_factory,
        discovery_responses={},
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
    )
    return TestClient(app), session_factory


def seed_feedback_case(session_factory: object, entries: list[dict[str, object]]) -> None:
    with session_scope(session_factory) as session:
        for source in entries:
            session.add(
                Source(
                    id=source["source_id"],
                    display_name=source["source_name"],
                    original_url=f"https://{source['source_name'].lower()}.example",
                    status="ready",
                )
            )

        for entry in entries:
            session.add(
                Post(
                    id=entry["post_id"],
                    source_id=entry["source_id"],
                    canonical_url=f"https://posts.example/{entry['post_id']}",
                    title=f"Post {entry['post_id']}",
                    published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                    raw_content="Seeded content.",
                    content_hash=f"post-{entry['post_id']}",
                    ingest_metadata='{"strategy":"feed"}',
                )
            )
            session.add(Feedback(post_id=entry["post_id"], state=entry["state"]))
            session.add(
                PostAnalysis(
                    post_id=entry["post_id"],
                    summary_ru="Seeded summary.",
                    metadata_json=json.dumps(entry["metadata"], sort_keys=True),
                )
            )


def test_get_preferences_returns_persisted_aggregate_explanations() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="Distributed tracing in practice",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Deep incident review.",
                content_hash="alpha-1",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))
        session.add(
            Post(
                id=2,
                source_id=1,
                canonical_url="https://alpha.example/posts/2",
                title="Opinionated frontend note",
                published_at=datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
                raw_content="Short take.",
                content_hash="alpha-2",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(Feedback(post_id=2, state="not_interesting"))
        session.add(
            PostAnalysis(
                post_id=1,
                summary_ru="Русское summary.",
                metadata_json=json.dumps(
                    {
                        "topics": ["observability", "distributed-systems"],
                        "format": "postmortem",
                        "technical_depth": "deep",
                        "verdict": "interesting",
                        "verdict_reason": "Dense practical engineering notes.",
                    },
                    sort_keys=True,
                ),
            )
        )
        session.add(
            PostAnalysis(
                post_id=2,
                summary_ru="Short summary.",
                metadata_json=json.dumps(
                    {
                        "topics": ["frontend"],
                        "format": "opinion",
                        "technical_depth": "shallow",
                        "verdict": "skip",
                        "verdict_reason": "Not practical enough.",
                    },
                    sort_keys=True,
                ),
            )
        )

    response = client.get("/api/preferences")

    assert response.status_code == 200
    assert response.json() == {
        "summary": "From 2 feedback signals, the profile is learning toward distributed systems postmortems from Alpha and away from opinion pieces.",
        "positive_signals": [
            "1 positive signal for source Alpha",
            "1 positive signal for topic distributed systems",
            "1 positive signal for format postmortem",
            "1 positive signal for deep technical material",
        ],
        "negative_signals": [
            "1 not-interesting signal against topic frontend",
            "1 not-interesting signal against format opinion",
        ],
        "learning_proof": [
            "2 feedback decisions recorded: 1 interesting, 0 want to read, 1 not interesting.",
            "Strongest positive pull: source Alpha and topic distributed systems.",
            "Strongest negative pull: topic frontend and format opinion.",
        ],
        "feedback_totals": {
            "interesting": 1,
            "not_interesting": 1,
            "total": 2,
            "want_to_read": 0,
        },
    }

    with session_scope(session_factory) as session:
        persisted = session.get(PreferenceProfile, 1)

    assert persisted is not None
    assert (
        persisted.summary
        == "From 2 feedback signals, the profile is learning toward distributed systems postmortems from Alpha and away from opinion pieces."
    )


def test_recompute_preferences_rebuilds_and_persists() -> None:
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="Distributed tracing in practice",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Deep incident review.",
                content_hash="alpha-1",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))
        session.add(
            PostAnalysis(
                post_id=1,
                summary_ru="Русское summary.",
                metadata_json=json.dumps(
                    {"topics": ["observability"], "format": "postmortem", "technical_depth": "deep"},
                    sort_keys=True,
                ),
            )
        )

    response = client.post("/api/preferences/recompute")

    assert response.status_code == 200
    assert response.json()["feedback_totals"]["interesting"] == 1

    with session_scope(session_factory) as session:
        persisted = session.get(PreferenceProfile, 1)
    assert persisted is not None
    assert "Alpha" in persisted.summary


def test_get_preferences_counts_feedback_without_analysis() -> None:
    """GOO-48: feedback for posts with no PostAnalysis must still be counted."""
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="Post without analysis",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Content here.",
                content_hash="no-analysis-hash",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))
        # Intentionally NO PostAnalysis for post 1

    response = client.get("/api/preferences")

    assert response.status_code == 200
    body = response.json()
    assert body["feedback_totals"]["interesting"] == 1
    assert body["feedback_totals"]["total"] == 1


def test_get_preferences_uses_stable_tie_breakers_when_counts_match() -> None:
    ordered_client, ordered_session_factory = build_client()
    reversed_client, reversed_session_factory = build_client()

    ordered_entries = [
        {
            "post_id": 1,
            "source_id": 1,
            "source_name": "Beta",
            "state": "interesting",
            "metadata": {
                "topics": ["observability"],
                "format": "postmortem",
                "technical_depth": "deep",
            },
        },
        {
            "post_id": 2,
            "source_id": 2,
            "source_name": "Alpha",
            "state": "want_to_read",
            "metadata": {
                "topics": ["ai"],
                "format": "guide",
                "technical_depth": "deep",
            },
        },
        {
            "post_id": 3,
            "source_id": 3,
            "source_name": "Gamma",
            "state": "not_interesting",
            "metadata": {
                "topics": ["frontend"],
                "format": "opinion",
                "technical_depth": "shallow",
            },
        },
        {
            "post_id": 4,
            "source_id": 4,
            "source_name": "Delta",
            "state": "not_interesting",
            "metadata": {
                "topics": ["cloud"],
                "format": "news",
                "technical_depth": "shallow",
            },
        },
    ]
    reversed_entries = list(reversed(ordered_entries))

    seed_feedback_case(ordered_session_factory, ordered_entries)
    seed_feedback_case(reversed_session_factory, reversed_entries)

    ordered_response = ordered_client.get("/api/preferences")
    reversed_response = reversed_client.get("/api/preferences")

    assert ordered_response.status_code == 200
    assert reversed_response.status_code == 200
    assert ordered_response.json() == reversed_response.json()
    assert ordered_response.json() == {
        "summary": "From 4 feedback signals, the profile is learning toward ai guides from Alpha and away from news.",
        "positive_signals": [
            "1 positive signal for source Alpha",
            "1 positive signal for topic ai",
            "1 positive signal for format guide",
            "2 positive signals for deep technical material",
        ],
        "negative_signals": [
            "1 not-interesting signal against topic cloud",
            "1 not-interesting signal against format news",
        ],
        "learning_proof": [
            "4 feedback decisions recorded: 1 interesting, 1 want to read, 2 not interesting.",
            "Strongest positive pull: source Alpha and topic ai.",
            "Strongest negative pull: topic cloud and format news.",
        ],
        "feedback_totals": {
            "interesting": 1,
            "not_interesting": 2,
            "total": 4,
            "want_to_read": 1,
        },
    }
