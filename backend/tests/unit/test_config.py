from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.core.request_auth import contract_token_verifier
from app.core.secrets import (
    APP_MASTER_KEY_SECRET_NAME,
    POSTGRES_PASSWORD_SECRET_NAME,
    InMemorySecretStore,
)


def test_settings_from_env_reads_defaults_and_overrides(monkeypatch) -> None:
    monkeypatch.delenv("GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN", raising=False)
    monkeypatch.delenv("GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN", raising=False)
    monkeypatch.delenv("GOOD_NEWS_POSTGRES_HOST", raising=False)
    monkeypatch.delenv("GOOD_NEWS_POSTGRES_PORT", raising=False)
    monkeypatch.delenv("GOOD_NEWS_POSTGRES_DATABASE", raising=False)
    monkeypatch.delenv("GOOD_NEWS_POSTGRES_USER", raising=False)
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_PORT", "6543")
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_DATABASE", "good_news_dev")
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_USER", "reader")

    settings = Settings.from_env()

    assert settings.postgres_host == "db.internal"
    assert settings.postgres_port == 6543
    assert settings.postgres_database == "good_news_dev"
    assert settings.postgres_user == "reader"
    assert settings.frontend_port == 5173
    assert settings.content_api_service_host == "localhost"
    assert settings.content_api_service_port == 8000
    assert settings.delivery_service_host == "localhost"
    assert settings.delivery_service_port == 8300


def test_settings_public_origin_urls_require_explicit_env_contract(monkeypatch) -> None:
    monkeypatch.delenv("GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN", raising=False)
    monkeypatch.delenv("GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN", raising=False)

    settings = Settings.from_env()

    try:
        settings.content_api_public_origin_url()
    except RuntimeError as exc:
        assert "GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN" in str(exc)
    else:  # pragma: no cover - defensive failure path
        raise AssertionError("Expected content API public origin lookup to fail without explicit env")

    try:
        settings.frontend_public_origin_url()
    except RuntimeError as exc:
        assert "GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN" in str(exc)
    else:  # pragma: no cover - defensive failure path
        raise AssertionError("Expected frontend public origin lookup to fail without explicit env")


def test_settings_public_origin_urls_prefer_explicit_env_contract(monkeypatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN", "https://api.good-news.test/")
    monkeypatch.setenv("GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN", "https://good-news.test/")

    settings = Settings.from_env()

    assert settings.content_api_public_origin_url() == "https://api.good-news.test"
    assert settings.frontend_public_origin_url() == "https://good-news.test"


def test_database_url_prefers_process_scoped_password(monkeypatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_PASSWORD", "env-secret")

    settings = Settings.from_env()

    assert settings.database_url() == "postgresql+psycopg://good_news:env-secret@localhost:5432/good_news"


def test_database_url_falls_back_to_secret_store(monkeypatch) -> None:
    monkeypatch.delenv("GOOD_NEWS_POSTGRES_PASSWORD", raising=False)
    settings = Settings.from_env()
    secret_store = InMemorySecretStore({POSTGRES_PASSWORD_SECRET_NAME: "credential-secret"})

    assert settings.database_url(secret_store=secret_store) == (
        "postgresql+psycopg://good_news:credential-secret@localhost:5432/good_news"
    )


def test_app_master_key_falls_back_to_secret_store(monkeypatch) -> None:
    monkeypatch.delenv("GOOD_NEWS_APP_MASTER_KEY", raising=False)
    settings = Settings.from_env()
    secret_store = InMemorySecretStore({APP_MASTER_KEY_SECRET_NAME: "master-key"})

    assert settings.app_master_key(secret_store=secret_store) == "master-key"


def test_fixed_now_is_an_explicit_utc_clock_contract(monkeypatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_FIXED_NOW", "2026-04-26T14:00:00+02:00")

    assert Settings.from_env().now() == datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


def test_fixed_now_rejects_a_timezone_less_value() -> None:
    with pytest.raises(ValueError, match="must include a timezone"):
        Settings(fixed_now="2026-04-26T12:00:00").now()


def test_contract_token_verifier_is_scoped_to_contract_environment() -> None:
    payload = '{"allowed":{"email":"reader@example.com","email_verified":true}}'

    assert contract_token_verifier(Settings(contract_auth_tokens_json=payload)) is None

    verifier = contract_token_verifier(
        Settings(environment="contract", contract_auth_tokens_json=payload)
    )

    assert verifier is not None
    assert verifier("allowed")["email"] == "reader@example.com"
    with pytest.raises(ValueError, match="Unknown contract token"):
        verifier("missing")
