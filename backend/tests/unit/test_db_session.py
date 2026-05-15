from sqlalchemy import select

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.setting import Setting, TechnicalEvent
from app.models.source import Source


def test_session_scope_commits_inserted_rows() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                display_name="OpenAI",
                original_url="https://developers.openai.com/blog",
                status="pending",
            )
        )

    with session_scope(session_factory) as session:
        stored_source = session.scalar(select(Source))

    assert stored_source is not None
    assert stored_source.original_url == "https://developers.openai.com/blog"
    assert stored_source.active is True


def test_session_scope_rolls_back_failed_transactions() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    try:
        with session_scope(session_factory) as session:
            session.add(Setting(key="digest.enabled", value="true"))
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with session_scope(session_factory) as session:
        assert session.scalar(select(Setting)) is None


def test_engine_supports_all_core_task_two_tables() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(TechnicalEvent(subsystem="source-sync", event_code="boot", summary="ok"))

    with session_scope(session_factory) as session:
        event = session.scalar(select(TechnicalEvent))

    assert event is not None
    assert event.event_code == "boot"
