import sys

import pytest

from app.core.secrets import (
    APP_MASTER_KEY_SECRET_NAME,
    POSTGRES_PASSWORD_SECRET_NAME,
    EnvironmentVariableSecretStore,
    InMemorySecretStore,
    SecretNotFoundError,
    WindowsCredentialManagerSecretStore,
    create_platform_secret_store,
)

_windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows Credential Manager only")


def test_secret_name_constants_match_runtime_contract() -> None:
    assert APP_MASTER_KEY_SECRET_NAME == "good-news/dev/app-master-key"
    assert POSTGRES_PASSWORD_SECRET_NAME == "good-news/dev/postgres-password"


def test_in_memory_secret_store_round_trips_values() -> None:
    secret_store = InMemorySecretStore()

    secret_store.set_secret(APP_MASTER_KEY_SECRET_NAME, "abc123")

    assert secret_store.get_secret(APP_MASTER_KEY_SECRET_NAME) == "abc123"
    assert secret_store.has_secret(APP_MASTER_KEY_SECRET_NAME) is True


def test_in_memory_secret_store_raises_for_missing_secret() -> None:
    secret_store = InMemorySecretStore()

    with pytest.raises(SecretNotFoundError):
        secret_store.get_secret(POSTGRES_PASSWORD_SECRET_NAME)


def test_env_secret_store_reads_app_master_key(monkeypatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_APP_MASTER_KEY", "my-master-key")

    secret_store = EnvironmentVariableSecretStore()

    assert secret_store.get_secret(APP_MASTER_KEY_SECRET_NAME) == "my-master-key"


def test_env_secret_store_reads_postgres_password(monkeypatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_PASSWORD", "pg-pass")

    secret_store = EnvironmentVariableSecretStore()

    assert secret_store.get_secret(POSTGRES_PASSWORD_SECRET_NAME) == "pg-pass"


def test_env_secret_store_raises_for_missing_env_var(monkeypatch) -> None:
    monkeypatch.delenv("GOOD_NEWS_APP_MASTER_KEY", raising=False)

    secret_store = EnvironmentVariableSecretStore()

    with pytest.raises(SecretNotFoundError):
        secret_store.get_secret(APP_MASTER_KEY_SECRET_NAME)


def test_env_secret_store_raises_with_diagnostic_for_empty_env_var(monkeypatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_APP_MASTER_KEY", "")

    secret_store = EnvironmentVariableSecretStore()

    with pytest.raises(SecretNotFoundError, match="set but empty"):
        secret_store.get_secret(APP_MASTER_KEY_SECRET_NAME)


def test_env_secret_store_has_secret_true_when_env_var_set(monkeypatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_APP_MASTER_KEY", "some-value")

    secret_store = EnvironmentVariableSecretStore()

    assert secret_store.has_secret(APP_MASTER_KEY_SECRET_NAME) is True


def test_env_secret_store_has_secret_false_when_env_var_not_set(monkeypatch) -> None:
    monkeypatch.delenv("GOOD_NEWS_APP_MASTER_KEY", raising=False)

    secret_store = EnvironmentVariableSecretStore()

    assert secret_store.has_secret(APP_MASTER_KEY_SECRET_NAME) is False


@_windows_only
def test_create_platform_secret_store_returns_windows_store_on_win32() -> None:
    store = create_platform_secret_store()

    assert isinstance(store, WindowsCredentialManagerSecretStore)
    assert hasattr(store, "_read_secret_bytes")


def test_create_platform_secret_store_returns_none_on_non_windows(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")

    store = create_platform_secret_store()

    assert store is None


@_windows_only
def test_windows_secret_store_decodes_generic_credential(monkeypatch) -> None:
    monkeypatch.setattr(
        WindowsCredentialManagerSecretStore,
        "_read_secret_bytes",
        staticmethod(lambda target_name: "stored-value".encode("utf-16-le")),
    )

    secret_store = WindowsCredentialManagerSecretStore()

    assert secret_store.get_secret(APP_MASTER_KEY_SECRET_NAME) == "stored-value"
    assert secret_store.has_secret(APP_MASTER_KEY_SECRET_NAME) is True
