from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.content_api_service.main import create_app
from app.models.base import Base
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.source import Source
from app.testing.schema import stamp_schema_head


def build_client(*, frontend_origin: str | None = None) -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    app = create_app(
        session_factory=session_factory,
        discovery_responses={},
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        settings=None
        if frontend_origin is None
        else Settings(public_frontend_origin=frontend_origin),
    )
    return TestClient(app), session_factory


def test_feedback_link_persists_state_and_redirects_to_explicit_public_frontend_origin() -> None:
    client, session_factory = build_client(frontend_origin="https://good-news.example")

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh enough for the default window.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    response = client.get("/api/feedback/1/want_to_read?digest_id=21", follow_redirects=False)

    assert response.status_code == 307
    parsed = urlparse(response.headers["location"])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://good-news.example/want-to-read"
    assert parse_qs(parsed.query) == {
        "digest_id": ["21"],
        "feedback": ["want_to_read"],
        "from": ["digest_email"],
        "post_id": ["1"],
    }

    with session_scope(session_factory) as session:
        feedback = session.query(Feedback).filter(Feedback.post_id == 1).one()

    assert feedback.state == "want_to_read"


def test_feedback_link_prefers_explicit_public_frontend_origin(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GOOD_NEWS_FRONTEND_PORT", "55173")
    monkeypatch.setenv("GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN", "https://good-news.example")
    client, session_factory = build_client()

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh enough for the default window.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    response = client.get("/api/feedback/1/want_to_read?digest_id=21", follow_redirects=False)

    assert response.status_code == 307
    parsed = urlparse(response.headers["location"])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://good-news.example/want-to-read"
    assert parse_qs(parsed.query)["digest_id"] == ["21"]


def test_feedback_link_redirects_digest_email_reactions_back_to_digest_history() -> None:
    client, session_factory = build_client(frontend_origin="https://good-news.example")

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh enough for the default window.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    response = client.get("/api/feedback/1/interesting?digest_id=21", follow_redirects=False)

    assert response.status_code == 307
    parsed = urlparse(response.headers["location"])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://good-news.example/digests"
    assert parse_qs(parsed.query) == {
        "digest_id": ["21"],
        "feedback": ["interesting"],
        "from": ["digest_email"],
        "post_id": ["1"],
    }


def test_put_feedback_persists_and_updates_state_for_in_app_actions() -> None:
    client, session_factory = build_client(frontend_origin="https://good-news.example")

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh enough for the default window.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    first_response = client.put("/api/feedback/1", json={"state": "interesting"})

    assert first_response.status_code == 200
    assert first_response.json() == {"post_id": 1, "state": "interesting"}

    with session_scope(session_factory) as session:
        feedback = session.query(Feedback).filter(Feedback.post_id == 1).one()

    assert feedback.state == "interesting"

    second_response = client.put("/api/feedback/1", json={"state": "want_to_read"})

    assert second_response.status_code == 200
    assert second_response.json() == {"post_id": 1, "state": "want_to_read"}

    with session_scope(session_factory) as session:
        updated_feedback = session.query(Feedback).filter(Feedback.post_id == 1).one()

    assert updated_feedback.state == "want_to_read"


def test_put_want_to_read_persists_and_clears_saved_state() -> None:
    client, session_factory = build_client(frontend_origin="https://good-news.example")

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh enough for the default window.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )

    save_response = client.put("/api/want-to-read/1", json={"saved": True})

    assert save_response.status_code == 200
    assert save_response.json() == {"post_id": 1, "saved": True, "feedback_state": "want_to_read"}

    with session_scope(session_factory) as session:
        saved_feedback = session.query(Feedback).filter(Feedback.post_id == 1).one()

    assert saved_feedback.state == "want_to_read"

    clear_response = client.put("/api/want-to-read/1", json={"saved": False})

    assert clear_response.status_code == 200
    assert clear_response.json() == {"post_id": 1, "saved": False, "feedback_state": None}

    with session_scope(session_factory) as session:
        cleared_feedback = session.query(Feedback).filter(Feedback.post_id == 1).one_or_none()

    assert cleared_feedback is None


def test_put_want_to_read_false_preserves_non_saved_feedback_state() -> None:
    client, session_factory = build_client(frontend_origin="https://good-news.example")

    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Alpha One",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="Fresh enough for the default window.",
                content_hash="alpha-one",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))

    response = client.put("/api/want-to-read/1", json={"saved": False})

    assert response.status_code == 200
    assert response.json() == {"post_id": 1, "saved": False, "feedback_state": "interesting"}

    with session_scope(session_factory) as session:
        feedback = session.query(Feedback).filter(Feedback.post_id == 1).one()

    assert feedback.state == "interesting"
