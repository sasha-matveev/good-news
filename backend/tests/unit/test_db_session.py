import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.db import (
    DatabaseUnavailableError,
    create_engine_from_url,
    create_session_factory,
    session_scope,
    wait_for_database,
)
from app.models.base import Base
from app.models.setting import Setting
from app.models.source import Source


class _FakeSession:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def execute(self, *args: object, **kwargs: object) -> None:
        if self._fail:
            raise OperationalError("SELECT 1", None, Exception("connection refused"))


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


def test_postgres_engine_revalidates_idle_connections() -> None:
    # Neon suspends compute and drops idle connections; the engine must pre-ping on
    # checkout and recycle stale connections so the first request after an idle
    # period reconnects instead of 500-ing on a dead pooled connection.
    engine = create_engine_from_url("postgresql+psycopg://u:p@localhost:5432/db")

    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 1800


def test_sqlite_engine_keeps_default_pool_behavior() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")

    assert engine.pool._pre_ping is False
    assert engine.pool._recycle == -1


def test_wait_for_database_returns_when_db_is_reachable() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    session_factory = create_session_factory(engine)

    # Reachable DB: returns without sleeping or hitting the deadline.
    wait_for_database(session_factory, sleep=lambda _: pytest.fail("should not sleep"))


def test_wait_for_database_retries_transient_failures_then_succeeds() -> None:
    attempts = {"n": 0}
    sleeps: list[float] = []

    def factory() -> _FakeSession:
        attempts["n"] += 1
        return _FakeSession(fail=attempts["n"] <= 2)

    # monotonic pinned to 0 -> deadline never reached, so it keeps retrying until ok.
    wait_for_database(
        factory,
        sleep=sleeps.append,
        monotonic=lambda: 0.0,
    )

    assert attempts["n"] == 3
    assert sleeps == [1.0, 1.0]


def test_wait_for_database_gives_up_after_timeout() -> None:
    sleeps: list[float] = []
    clock = iter([0.0, 10.0, 20.0, 31.0])  # deadline = 0 + 30

    def factory() -> _FakeSession:
        return _FakeSession(fail=True)

    with pytest.raises(DatabaseUnavailableError):
        wait_for_database(
            factory,
            sleep=sleeps.append,
            monotonic=lambda: next(clock),
        )

    # Retried within the window, then failed once past the deadline.
    assert sleeps == [1.0, 1.0]
