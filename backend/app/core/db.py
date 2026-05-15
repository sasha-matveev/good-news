from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.secrets import SecretStore


def create_engine_from_url(database_url: str, echo: bool = False) -> Engine:
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
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
