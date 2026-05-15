from __future__ import annotations

import os
import time
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.core.config import Settings
from app.models.setting import Setting
from app.services.email_service import EmailMessage, SmtpTransport, send_email


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured for this integration run.")
    return value


def test_ephemeral_postgres_round_trips_settings_write() -> None:
    _require_env("GOOD_NEWS_POSTGRES_HOST")
    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    unique_key = f"phase2-integration-{uuid4()}"

    with session_scope(session_factory) as session:
        session.add(Setting(key=unique_key, value="ready"))

    with session_scope(session_factory) as session:
        persisted = session.scalar(select(Setting).where(Setting.key == unique_key))

    assert persisted is not None
    assert persisted.value == "ready"


def test_ephemeral_smtp_sink_captures_sent_message() -> None:
    smtp_host = _require_env("GOOD_NEWS_TEST_SMTP_HOST")
    smtp_port = int(_require_env("GOOD_NEWS_TEST_SMTP_PORT"))
    smtp_api_url = _require_env("GOOD_NEWS_TEST_SMTP_API_URL")

    with httpx.Client(timeout=5.0) as client:
        before_total = client.get(smtp_api_url).json()["total"]

    send_email(
        EmailMessage(
            sender="digest@example.com",
            recipient="reader@example.com",
            subject="Phase 2 SMTP integration",
            html_body="<p>phase 2 verification</p>",
        ),
        transport=SmtpTransport(
            host=smtp_host,
            port=smtp_port,
            username=None,
            password=None,
            security_mode="none",
        ),
    )

    deadline = time.time() + 10
    with httpx.Client(timeout=5.0) as client:
        while time.time() < deadline:
            payload = client.get(smtp_api_url).json()
            if payload["total"] > before_total:
                break
            time.sleep(1)
        else:
            raise AssertionError("MailHog did not capture the SMTP test email in time.")

    assert payload["total"] > before_total
