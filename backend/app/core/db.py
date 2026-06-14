from __future__ import annotations

import time
from contextlib import contextmanager
from collections.abc import Callable, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.secrets import SecretStore

# How long startup waits for a cold Neon instance to accept connections before
# giving up, and how often it retries within that window.
DATABASE_READY_TIMEOUT_SECONDS = 30.0
DATABASE_READY_POLL_INTERVAL_SECONDS = 1.0


class DatabaseUnavailableError(RuntimeError):
    """Raised when the database stays unreachable past the readiness timeout."""


def create_engine_from_url(database_url: str, echo: bool = False) -> Engine:
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        # Neon (serverless Postgres) suspends compute and drops idle connections.
        # Without pre_ping a pooled connection Neon has already closed is handed out
        # and the first query raises OperationalError -> the request 500s. pre_ping
        # revalidates on checkout and transparently reconnects; recycle caps the
        # connection age below Neon's idle window so we rarely hit a dropped one.
        # connect_timeout bounds each attempt so a cold instance fails fast and is
        # retried by wait_for_database instead of hanging.
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = 1800
        connect_args["connect_timeout"] = 5
    if database_url.endswith(":memory:"):
        engine_kwargs["poolclass"] = StaticPool
    return create_engine(database_url, echo=echo, connect_args=connect_args, **engine_kwargs)


def create_engine_from_settings(
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
    echo: bool = False,
) -> Engine:
    resolved_settings = settings or Settings.from_env()
    return create_engine_from_url(
        resolved_settings.database_url(secret_store=secret_store),
        echo=echo,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def wait_for_database(
    session_factory: sessionmaker[Session],
    *,
    timeout_seconds: float = DATABASE_READY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DATABASE_READY_POLL_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """Block until the database answers a trivial query.

    Cloud Run cold-starts against a Neon instance that may still be waking up; a
    single failed connect would crash startup and surface as a 503. Transient
    connection failures are retried for a bounded window and we only give up —
    failing the container — if the database is still unreachable after
    ``timeout_seconds``. Schema correctness is deliberately *not* checked here; a
    genuine schema mismatch must keep failing fast rather than being retried.
    """
    deadline = monotonic() + timeout_seconds
    while True:
        try:
            with session_factory() as session:
                session.execute(text("SELECT 1"))
            return
        except (OperationalError, InterfaceError) as exc:
            if monotonic() >= deadline:
                raise DatabaseUnavailableError(
                    f"Database did not become reachable within {timeout_seconds:.0f}s."
                ) from exc
            sleep(poll_interval_seconds)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
