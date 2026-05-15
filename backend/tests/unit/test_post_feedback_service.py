from __future__ import annotations

from app.models.base import Base
from app.models.feedback import Feedback
from app.models.post import Post
from app.models.read_later import ReadLater
from app.models.source import Source
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.services.read_later_service import toggle_read_later


def build_session_factory():
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def _seed_post(session_factory, post_id: int = 1) -> None:
    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=post_id,
                source_id=1,
                canonical_url=f"https://alpha.example/posts/{post_id}",
                title=f"Post {post_id}",
                raw_content="Content.",
                content_hash=f"hash-{post_id}",
                ingest_metadata='{"strategy":"feed"}',
            )
        )


def test_toggle_read_later_saves_when_not_present() -> None:
    sf = build_session_factory()
    _seed_post(sf)

    with session_scope(sf) as session:
        result = toggle_read_later(session, post_id=1, saved=True)

    assert result is True

    with session_scope(sf) as session:
        row = session.query(ReadLater).filter(ReadLater.post_id == 1).one()
    assert row is not None


def test_toggle_read_later_removes_when_present() -> None:
    sf = build_session_factory()
    _seed_post(sf)

    with session_scope(sf) as session:
        session.add(ReadLater(post_id=1))

    with session_scope(sf) as session:
        result = toggle_read_later(session, post_id=1, saved=False)

    assert result is False

    with session_scope(sf) as session:
        row = session.query(ReadLater).filter(ReadLater.post_id == 1).one_or_none()
    assert row is None


def test_toggle_read_later_idempotent_save() -> None:
    """Saving when already saved must not create duplicate rows."""
    sf = build_session_factory()
    _seed_post(sf)

    with session_scope(sf) as session:
        session.add(ReadLater(post_id=1))

    with session_scope(sf) as session:
        result = toggle_read_later(session, post_id=1, saved=True)

    assert result is True

    with session_scope(sf) as session:
        count = session.query(ReadLater).filter(ReadLater.post_id == 1).count()
    assert count == 1


def test_toggle_read_later_idempotent_clear() -> None:
    """Clearing when nothing exists must succeed and return False."""
    sf = build_session_factory()
    _seed_post(sf)

    with session_scope(sf) as session:
        result = toggle_read_later(session, post_id=1, saved=False)

    assert result is False


def test_toggle_read_later_does_not_affect_feedback_state() -> None:
    sf = build_session_factory()
    _seed_post(sf)

    with session_scope(sf) as session:
        session.add(Feedback(post_id=1, state="interesting"))

    with session_scope(sf) as session:
        toggle_read_later(session, post_id=1, saved=True)

    with session_scope(sf) as session:
        feedback = session.query(Feedback).filter(Feedback.post_id == 1).one()
    assert feedback.state == "interesting"
