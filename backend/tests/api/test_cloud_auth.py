from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory
from app.main import create_app
from app.models.base import Base
from app.testing.schema import stamp_schema_head


def _build_app(settings: Settings):
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    return create_app(
        session_factory=session_factory,
        responses={},
        settings=settings,
        analysis_client_factory=lambda: object(),
    )


AUTH_SETTINGS = Settings(
    firebase_project_id="good-news-test",
    allowed_emails="owner@example.com",
    scheduler_invoker="scheduler@test.iam.gserviceaccount.com",
)


def test_api_requires_bearer_token_when_firebase_auth_configured() -> None:
    app = _build_app(AUTH_SETTINGS)
    with TestClient(app) as client:
        response = client.get("/api/posts")
    assert response.status_code == 401
    assert response.headers["X-Good-News-Backend"] == "python"


def test_api_health_stays_public() -> None:
    app = _build_app(AUTH_SETTINGS)
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200


def test_browser_preflight_matches_frontend_authorization_contract() -> None:
    app = _build_app(
        Settings(
            firebase_project_id="good-news-test",
            allowed_emails="owner@example.com",
            public_frontend_origin="https://good-news.example",
        )
    )
    with TestClient(app) as client:
        response = client.options(
            "/api/posts",
            headers={
                "Origin": "https://good-news.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,x-correlation-id",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://good-news.example"
    assert "Authorization" in response.headers["access-control-allow-headers"]
    assert response.headers["X-Good-News-Backend"] == "python"


def test_correlation_id_is_preserved_on_response() -> None:
    app = _build_app(Settings())
    with TestClient(app) as client:
        response = client.get(
            "/api/health", headers={"X-Correlation-ID": "frontend-request-42"}
        )

    assert response.headers["X-Correlation-ID"] == "frontend-request-42"


def test_api_rejects_non_allowlisted_email() -> None:
    app = _build_app(AUTH_SETTINGS)
    app.state.user_token_verifier = lambda token: {
        "email": "stranger@example.com",
        "email_verified": True,
    }
    with TestClient(app) as client:
        response = client.get("/api/posts", headers={"Authorization": "Bearer x"})
    assert response.status_code == 403


def test_api_accepts_allowlisted_verified_email() -> None:
    app = _build_app(AUTH_SETTINGS)
    app.state.user_token_verifier = lambda token: {
        "email": "owner@example.com",
        "email_verified": True,
    }
    with TestClient(app) as client:
        response = client.get("/api/posts", headers={"Authorization": "Bearer x"})
    assert response.status_code == 200


def test_api_open_when_firebase_auth_not_configured() -> None:
    app = _build_app(Settings())
    with TestClient(app) as client:
        response = client.get("/api/posts")
    assert response.status_code == 200


def test_internal_job_requires_oidc_token() -> None:
    app = _build_app(AUTH_SETTINGS)
    with TestClient(app) as client:
        response = client.post("/internal/jobs/source-sync")
    assert response.status_code == 401


def test_internal_job_unavailable_without_invoker_configuration() -> None:
    app = _build_app(Settings())
    with TestClient(app) as client:
        response = client.post("/internal/jobs/source-sync")
    assert response.status_code == 503


def test_internal_job_rejects_wrong_service_account() -> None:
    app = _build_app(AUTH_SETTINGS)
    app.state.scheduler_oidc_verifier = lambda token: {
        "email": "intruder@test.iam.gserviceaccount.com",
        "email_verified": True,
    }
    with TestClient(app) as client:
        response = client.post(
            "/internal/jobs/source-sync", headers={"Authorization": "Bearer x"}
        )
    assert response.status_code == 403


def test_internal_source_sync_runs_for_scheduler_service_account() -> None:
    app = _build_app(AUTH_SETTINGS)
    app.state.scheduler_oidc_verifier = lambda token: {
        "email": "scheduler@test.iam.gserviceaccount.com",
        "email_verified": True,
    }
    with TestClient(app) as client:
        response = client.post(
            "/internal/jobs/source-sync", headers={"Authorization": "Bearer x"}
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_source_ids"] == []
