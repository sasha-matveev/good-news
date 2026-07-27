from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory
from app.content_api_service.main import create_app
from app.models.base import Base
from app.testing.schema import stamp_schema_head


def test_content_api_startup_fails_when_schema_not_ready() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app(session_factory=session_factory, discovery_responses={})

    with pytest.raises(
        RuntimeError,
        match="Database schema is not current; run `gcloud run jobs execute db-migrate --wait`\\.",
    ):
        with TestClient(app):
            pass


def test_health_reports_ok_after_schema_is_current() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    app = create_app(session_factory=session_factory, discovery_responses={})
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Good-News-Backend"] == "python"
    assert response.headers["X-Correlation-ID"]
