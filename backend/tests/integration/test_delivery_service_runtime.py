from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.delivery_service.main import create_app
from app.models.digest import Digest
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.setting import SecretSetting, Setting
from app.models.source import Source
from app.services.settings_service import encrypt_secret
from app.testing.schema import stamp_schema_head


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured for this integration run.")
    return value


def _reset_runtime_state(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.execute(text("DELETE FROM digest_items"))
        session.execute(text("DELETE FROM digests"))
        session.execute(text("DELETE FROM feedback"))
        session.execute(text("DELETE FROM post_analysis"))
        session.execute(text("DELETE FROM posts"))
        session.execute(text("DELETE FROM technical_events"))
        session.execute(text("DELETE FROM sources"))
        session.execute(
            text(
                "DELETE FROM secret_settings WHERE key = 'smtp_password'"
            )
        )
        session.execute(
            text(
                "DELETE FROM settings WHERE key IN ('recipient_email','sender_identity','smtp_host','smtp_port','smtp_username','smtp_security_mode','daily_digest_enabled','daily_digest_catch_up_enabled','last_daily_digest_sent_at')"
            )
        )


def test_delivery_service_runtime_sends_digest_and_updates_history() -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    _require_env("GOOD_NEWS_TEST_SMTP_API_URL")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)
    unique_url = f"https://delivery-runtime.example/{uuid4()}"
    master_key = _require_env("GOOD_NEWS_APP_MASTER_KEY")

    _reset_runtime_state(session_factory)

    with session_scope(session_factory) as session:
        session.add_all(
            [
                Setting(key="recipient_email", value="reader@example.com"),
                Setting(key="sender_identity", value="Good News Digest <digest@example.com>"),
                Setting(key="smtp_host", value=_require_env("GOOD_NEWS_TEST_SMTP_HOST")),
                Setting(key="smtp_port", value=_require_env("GOOD_NEWS_TEST_SMTP_PORT")),
                Setting(key="smtp_security_mode", value="none"),
                Setting(key="daily_digest_enabled", value="true"),
                Setting(key="daily_digest_catch_up_enabled", value="true"),
            ]
        )
        session.add(
            SecretSetting(
                key="smtp_password",
                encrypted_value=encrypt_secret("unused", master_key),
            )
        )
        source = Source(display_name="Runtime", original_url=unique_url, status="ready")
        session.add(source)
        session.flush()
        post = Post(
            source_id=source.id,
            canonical_url=f"{unique_url}/post",
            title="Delivery Runtime Post",
            published_at=None,
            raw_content="Runtime delivery content.",
            content_hash=f"delivery-{uuid4()}",
            ingest_metadata="{}",
        )
        session.add(post)
        session.flush()
        session.add(
            PostAnalysis(
                post_id=post.id,
                summary_ru="Runtime delivery summary.",
                metadata_json=json.dumps(
                    {
                        "topics": ["runtime"],
                        "format": "article",
                        "technical_depth": "medium",
                        "verdict": "interesting",
                        "verdict_reason": "Runtime delivery proof.",
                    }
                ),
            )
        )

    app = create_app(session_factory=session_factory, settings=Settings.from_env(), enable_scheduler=False)
    client = TestClient(app)

    test_email_response = client.post("/internal/delivery/test-email")
    assert test_email_response.status_code == 200

    run_once_response = client.post("/internal/delivery/digests/run-once")
    assert run_once_response.status_code == 200
    assert run_once_response.json()["status"] == "sent"
    assert run_once_response.json()["delivered"] is True

    with session_scope(session_factory) as session:
        digest = session.scalar(select(Digest).where(Digest.id == run_once_response.json()["digest_id"]))
        sent_setting = session.scalar(select(Setting).where(Setting.key == "last_daily_digest_sent_at"))

    assert digest is not None
    assert digest.status == "sent"
    assert digest.recipient_email == "reader@example.com"
    assert digest.sent_at is not None
    assert digest.html_body is not None
    assert _require_env("GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN") in digest.html_body
    assert sent_setting is not None
    assert sent_setting.value is not None
