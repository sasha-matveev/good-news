from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory
from app.content_api_service.main import create_app
from app.models.base import Base
from app.testing.schema import stamp_schema_head


def test_health_endpoint_returns_ok_status() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    client = TestClient(create_app(session_factory=session_factory, discovery_responses={}))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
