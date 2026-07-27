from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.analysis_llm_service.main import create_app as create_analysis_app
from app.content_api_service.main import create_app as create_content_api_app
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.core.schema_guard import expected_revision
from app.delivery_service.main import create_app as create_delivery_app
from app.main import create_app as create_monolith_app
from app.models.base import Base
from app.source_ingestion_service.main import create_app as create_ingestion_app


@pytest.mark.parametrize(
    ("app_factory", "kwargs"),
    [
        (create_monolith_app, {}),
        (create_content_api_app, {"discovery_responses": {}}),
        (create_analysis_app, {}),
        (create_ingestion_app, {"enable_scheduler": False}),
        (create_delivery_app, {"enable_scheduler": False}),
    ],
)
def test_service_startup_fails_clearly_when_schema_is_not_ready(app_factory, kwargs: dict[str, object]) -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = app_factory(session_factory=session_factory, **kwargs)

    with pytest.raises(
        RuntimeError,
        match="Database schema is not current; run `gcloud run jobs execute db-migrate --wait`\\.",
    ):
        with TestClient(app):
            pass


@pytest.mark.parametrize(
    ("app_factory", "kwargs"),
    [
        (create_monolith_app, {}),
        (create_content_api_app, {"discovery_responses": {}}),
        (create_analysis_app, {}),
        (create_ingestion_app, {"enable_scheduler": False}),
        (create_delivery_app, {"enable_scheduler": False}),
    ],
)
def test_service_startup_succeeds_after_explicit_migration_marker(app_factory, kwargs: dict[str, object]) -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        session.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": expected_revision()},
        )
    app = app_factory(session_factory=session_factory, **kwargs)

    with TestClient(app):
        pass
