from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.content_api_service.main import create_app
from app.models.base import Base
from app.ai.gemini_client import DEFAULT_SUMMARY_INSTRUCTIONS, DEFAULT_VERDICT_REASON_INSTRUCTIONS
from app.models.setting import SecretSetting, Setting
from app.testing.schema import stamp_schema_head


def build_client() -> tuple[TestClient, object]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    app = create_app(
        session_factory=session_factory,
        discovery_responses={},
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
    )
    app.state.app_master_key = "test-master-key"
    return TestClient(app), session_factory


def test_settings_api_returns_defaults_and_persists_write_only_smtp_password() -> None:
    client, session_factory = build_client()

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "daily_digest_time": "12:00",
        "weekly_digest_day_of_week": "sat",
        "weekly_digest_time": "23:30",
        "observability_dashboard_url": "http://127.0.0.1:3000/d/good-news-overview/good-news-observability-overview",
        "recipient_email": None,
        "sender_identity": None,
        "smtp_host": None,
        "smtp_port": 587,
        "smtp_username": None,
        "smtp_security_mode": "starttls",
        "daily_digest_enabled": True,
        "daily_digest_catch_up_enabled": True,
        "weekly_digest_enabled": False,
        "weekly_digest_catch_up_enabled": True,
        "smtp_password_configured": False,
        "analysis_summary_prompt": DEFAULT_SUMMARY_INSTRUCTIONS,
        "analysis_verdict_reason_prompt": DEFAULT_VERDICT_REASON_INSTRUCTIONS,
    }

    update_response = client.put(
        "/api/settings",
        json={
            "daily_digest_time": "08:45",
            "weekly_digest_day_of_week": "fri",
            "weekly_digest_time": "16:30",
            "recipient_email": "reader@example.com",
            "sender_identity": "Good News Digest <digest@example.com>",
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "smtp_username": "digest-user",
            "smtp_security_mode": "ssl",
            "daily_digest_enabled": True,
            "daily_digest_catch_up_enabled": False,
            "weekly_digest_enabled": True,
            "weekly_digest_catch_up_enabled": False,
            "smtp_password": "plain-secret",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "daily_digest_time": "08:45",
        "weekly_digest_day_of_week": "fri",
        "weekly_digest_time": "16:30",
        "observability_dashboard_url": "http://127.0.0.1:3000/d/good-news-overview/good-news-observability-overview",
        "recipient_email": "reader@example.com",
        "sender_identity": "Good News Digest <digest@example.com>",
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_username": "digest-user",
        "smtp_security_mode": "ssl",
        "daily_digest_enabled": True,
        "daily_digest_catch_up_enabled": False,
        "weekly_digest_enabled": True,
        "weekly_digest_catch_up_enabled": False,
        "smtp_password_configured": True,
        # PUT omitted the prompt fields → they fall back to the defaults.
        "analysis_summary_prompt": DEFAULT_SUMMARY_INSTRUCTIONS,
        "analysis_verdict_reason_prompt": DEFAULT_VERDICT_REASON_INSTRUCTIONS,
    }
    assert "plain-secret" not in update_response.text

    read_after_write_response = client.get("/api/settings")

    assert read_after_write_response.status_code == 200
    assert read_after_write_response.json() == update_response.json()

    with session_scope(session_factory) as session:
        time_setting = session.query(Setting).filter(Setting.key == "daily_digest_time").one()
        password_setting = session.query(SecretSetting).filter(SecretSetting.key == "smtp_password").one()

    assert time_setting.value == "08:45"
    assert password_setting.encrypted_value != "plain-secret"


def _base_update_payload() -> dict:
    return {
        "daily_digest_time": "12:00",
        "weekly_digest_day_of_week": "sat",
        "weekly_digest_time": "23:30",
        "smtp_port": 587,
        "smtp_security_mode": "starttls",
        "daily_digest_enabled": True,
        "daily_digest_catch_up_enabled": True,
        "weekly_digest_enabled": False,
        "weekly_digest_catch_up_enabled": True,
    }


def test_settings_api_persists_custom_analysis_prompts_and_resets_on_blank() -> None:
    client, _ = build_client()

    custom_summary = "Дай короткое резюме на русском в одном предложении."
    custom_verdict = "One short English sentence on relevance."

    update_response = client.put(
        "/api/settings",
        json={
            **_base_update_payload(),
            "analysis_summary_prompt": custom_summary,
            "analysis_verdict_reason_prompt": custom_verdict,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["analysis_summary_prompt"] == custom_summary
    assert update_response.json()["analysis_verdict_reason_prompt"] == custom_verdict

    # GET reflects the persisted custom values.
    get_response = client.get("/api/settings")
    assert get_response.json()["analysis_summary_prompt"] == custom_summary
    assert get_response.json()["analysis_verdict_reason_prompt"] == custom_verdict

    # Blank/whitespace input resets to the defaults.
    reset_response = client.put(
        "/api/settings",
        json={
            **_base_update_payload(),
            "analysis_summary_prompt": "   ",
            "analysis_verdict_reason_prompt": "",
        },
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["analysis_summary_prompt"] == DEFAULT_SUMMARY_INSTRUCTIONS
    assert reset_response.json()["analysis_verdict_reason_prompt"] == DEFAULT_VERDICT_REASON_INSTRUCTIONS


def test_settings_api_rejects_invalid_daily_time() -> None:
    client, _ = build_client()

    response = client.put(
        "/api/settings",
        json={
            "daily_digest_time": "25:99",
            "weekly_digest_day_of_week": "mon",
            "weekly_digest_time": "12:00",
            "smtp_port": 587,
            "smtp_security_mode": "starttls",
            "daily_digest_enabled": True,
            "daily_digest_catch_up_enabled": True,
            "weekly_digest_enabled": False,
            "weekly_digest_catch_up_enabled": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "daily_digest_time"


def test_settings_api_rejects_invalid_weekly_schedule() -> None:
    client, _ = build_client()

    response = client.put(
        "/api/settings",
        json={
            "daily_digest_time": "12:00",
            "weekly_digest_day_of_week": "funday",
            "weekly_digest_time": "24:15",
            "smtp_port": 587,
            "smtp_security_mode": "starttls",
            "daily_digest_enabled": True,
            "daily_digest_catch_up_enabled": True,
            "weekly_digest_enabled": True,
            "weekly_digest_catch_up_enabled": True,
        },
    )

    assert response.status_code == 422
    invalid_fields = {item["loc"][-1] for item in response.json()["detail"]}
    assert invalid_fields == {"weekly_digest_day_of_week", "weekly_digest_time"}


def test_settings_test_email_delegates_to_delivery_boundary() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    delegated: dict[str, object] = {}

    class FakeDeliveryServiceClient:
        def send_test_email(self) -> dict[str, str]:
            delegated["called"] = True
            return {"status": "sent"}

    app = create_app(
        session_factory=session_factory,
        discovery_responses={},
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        delivery_service_client_factory=lambda: FakeDeliveryServiceClient(),
    )
    client = TestClient(app)

    response = client.post("/api/settings/test-email")

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    assert delegated["called"] is True


def test_settings_test_email_returns_bad_gateway_when_delivery_service_is_unavailable() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    class FailingDeliveryServiceClient:
        def send_test_email(self) -> dict[str, str]:
            raise httpx.ConnectError("delivery offline")

    app = create_app(
        session_factory=session_factory,
        discovery_responses={},
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        delivery_service_client_factory=lambda: FailingDeliveryServiceClient(),
    )
    client = TestClient(app)

    response = client.post("/api/settings/test-email")

    assert response.status_code == 502
    assert response.json() == {"detail": "Delivery service is unavailable."}
