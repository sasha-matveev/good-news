from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.delivery_service.main import create_app
from app.models.base import Base
from app.models.digest import Digest
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.setting import SecretSetting, Setting
from app.models.source import Source
from app.services.email_service import EmailSendError
from app.testing.schema import stamp_schema_head


class RecordingTransport:
    def __init__(self) -> None:
        self.sent_messages: list[object] = []

    def send(self, message) -> None:
        self.sent_messages.append(message)


def build_client() -> tuple[TestClient, object, RecordingTransport]:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    transport = RecordingTransport()
    app = create_app(
        session_factory=session_factory,
        settings=Settings(
            delivery_service_port=8300,
            frontend_port=5173,
            public_content_api_origin="https://api.good-news.example",
            public_frontend_origin="https://good-news.example",
            source_failure_threshold=2,
        ),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        email_transport_factory=lambda session: transport,
    )
    app.state.app_master_key = "test-master-key"
    return TestClient(app), session_factory, transport


def _seed_delivery_inputs(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.add_all(
            [
                Setting(key="recipient_email", value="reader@example.com"),
                Setting(key="sender_identity", value="Good News Digest <digest@example.com>"),
                Setting(key="smtp_host", value="smtp.example.com"),
                Setting(key="smtp_port", value="587"),
                Setting(key="smtp_security_mode", value="starttls"),
                Setting(key="daily_digest_enabled", value="true"),
                Setting(key="daily_digest_catch_up_enabled", value="true"),
            ]
        )
        session.add(SecretSetting(key="smtp_password", encrypted_value="encrypted-value"))
        session.add(Source(id=1, display_name="Alpha", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/1",
                title="Alpha Post",
                published_at=datetime(2026, 4, 26, 9, 0, tzinfo=UTC),
                raw_content="Alpha content",
                content_hash="alpha-hash",
                ingest_metadata="{}",
            )
        )
        session.add(
            PostAnalysis(
                post_id=1,
                summary_ru="Runtime summary",
                metadata_json='{"topics":["verification"],"format":"article","technical_depth":"medium","verdict":"interesting","verdict_reason":"Useful signal"}',
            )
        )


def test_delivery_service_health_test_email_and_run_once_digest() -> None:
    client, session_factory, transport = build_client()
    _seed_delivery_inputs(session_factory)

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    test_email_response = client.post("/internal/delivery/test-email")
    assert test_email_response.status_code == 200
    assert test_email_response.json() == {"status": "sent"}

    run_once_response = client.post("/internal/delivery/digests/run-once")
    assert run_once_response.status_code == 200
    assert run_once_response.json() == {"digest_id": 1, "status": "sent", "delivered": True, "item_count": 1}

    assert len(transport.sent_messages) == 2

    with session_scope(session_factory) as session:
        digest = session.scalar(select(Digest).where(Digest.id == 1))

    assert digest is not None
    assert digest.status == "sent"
    assert digest.recipient_email == "reader@example.com"
    assert digest.sent_at == datetime(2026, 4, 26, 12, 0)


def test_delivery_service_starts_when_catch_up_smtp_fails() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    with session_scope(session_factory) as session:
        session.add_all([
            Setting(key="recipient_email", value="reader@example.com"),
            Setting(key="daily_digest_enabled", value="true"),
            Setting(key="daily_digest_catch_up_enabled", value="true"),
        ])

    app = create_app(
        session_factory=session_factory,
        settings=Settings(
            delivery_service_port=8300,
            frontend_port=5173,
            public_content_api_origin="https://api.good-news.example",
            public_frontend_origin="https://good-news.example",
            source_failure_threshold=2,
        ),
        enable_scheduler=True,
        now_provider=lambda: datetime(2026, 4, 26, 14, 0, tzinfo=UTC),
    )

    with patch("app.delivery_service.main.catch_up_daily_digest_if_needed", side_effect=EmailSendError("SMTP unavailable")):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/health")

    assert response.status_code == 200, "Service must start even when catch-up email send fails"
