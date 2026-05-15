from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory
from app.content_api_service.main import create_app
from app.models.base import Base
from app.testing.schema import stamp_schema_head


def test_api_startup_does_not_own_background_scheduler() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    app = create_app(session_factory=session_factory, discovery_responses={})

    with TestClient(app):
        pass

    assert getattr(app.state, "scheduler", None) is None
