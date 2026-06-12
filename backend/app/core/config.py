from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from app.core.secrets import (
    APP_MASTER_KEY_SECRET_NAME,
    POSTGRES_PASSWORD_SECRET_NAME,
    SecretNotFoundError,
    SecretStore,
)


class MissingSecretError(RuntimeError):
    """Raised when a required runtime secret is not available."""


class MissingPublicOriginError(RuntimeError):
    """Raised when a required public origin is not configured."""


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


@dataclass(frozen=True)
class Settings:
    environment: str = "dev"
    content_api_service_host: str = "localhost"
    content_api_service_port: int = 8000
    frontend_port: int = 5173
    public_content_api_origin: str | None = None
    public_frontend_origin: str | None = None
    analysis_service_host: str = "localhost"
    analysis_service_port: int = 8100
    source_ingestion_service_host: str = "localhost"
    source_ingestion_service_port: int = 8200
    delivery_service_host: str = "localhost"
    delivery_service_port: int = 8300
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "good_news"
    postgres_user: str = "good_news"
    postgres_password_env_var: str = "GOOD_NEWS_POSTGRES_PASSWORD"
    app_master_key_env_var: str = "GOOD_NEWS_APP_MASTER_KEY"
    database_url_override: str | None = None
    analysis_stub_response_json: str | None = None
    ingestion_responses_json: str | None = None
    source_sync_interval_minutes: int = 30
    source_failure_threshold: int = 3
    gemini_api_key_env_var: str = "GOOD_NEWS_GEMINI_API_KEY"
    gemini_model: str = "gemini-2.5-flash-lite"
    firebase_project_id: str | None = None
    allowed_emails: str = ""
    scheduler_invoker: str | None = None
    oidc_audience: str | None = None
    observability_grafana_origin: str | None = None
    observability_grafana_host: str = "127.0.0.1"
    observability_grafana_host_port: int = 3000
    observability_daily_report_time: str = "18:00"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=os.getenv("GOOD_NEWS_ENV", "dev"),
            content_api_service_host=os.getenv("GOOD_NEWS_CONTENT_API_SERVICE_HOST", "localhost"),
            content_api_service_port=_read_int_env("GOOD_NEWS_CONTENT_API_SERVICE_PORT", 8000),
            frontend_port=_read_int_env("GOOD_NEWS_FRONTEND_PORT", 5173),
            public_content_api_origin=os.getenv("GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN"),
            public_frontend_origin=os.getenv("GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN"),
            analysis_service_host=os.getenv("GOOD_NEWS_ANALYSIS_SERVICE_HOST", "localhost"),
            analysis_service_port=_read_int_env("GOOD_NEWS_ANALYSIS_SERVICE_PORT", 8100),
            source_ingestion_service_host=os.getenv("GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST", "localhost"),
            source_ingestion_service_port=_read_int_env("GOOD_NEWS_SOURCE_INGESTION_SERVICE_PORT", 8200),
            delivery_service_host=os.getenv("GOOD_NEWS_DELIVERY_SERVICE_HOST", "localhost"),
            delivery_service_port=_read_int_env("GOOD_NEWS_DELIVERY_SERVICE_PORT", 8300),
            postgres_host=os.getenv("GOOD_NEWS_POSTGRES_HOST", "localhost"),
            postgres_port=_read_int_env("GOOD_NEWS_POSTGRES_PORT", 5432),
            postgres_database=os.getenv("GOOD_NEWS_POSTGRES_DATABASE", "good_news"),
            postgres_user=os.getenv("GOOD_NEWS_POSTGRES_USER", "good_news"),
            database_url_override=os.getenv("GOOD_NEWS_DATABASE_URL"),
            analysis_stub_response_json=os.getenv("GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON"),
            ingestion_responses_json=os.getenv("GOOD_NEWS_INGESTION_RESPONSES_JSON"),
            source_sync_interval_minutes=_read_int_env("GOOD_NEWS_SOURCE_SYNC_INTERVAL_MINUTES", 30),
            source_failure_threshold=_read_int_env("GOOD_NEWS_SOURCE_FAILURE_THRESHOLD", 3),
            gemini_model=os.getenv("GOOD_NEWS_GEMINI_MODEL", "gemini-2.5-flash-lite"),
            firebase_project_id=os.getenv("GOOD_NEWS_FIREBASE_PROJECT_ID"),
            allowed_emails=os.getenv("GOOD_NEWS_ALLOWED_EMAILS", ""),
            scheduler_invoker=os.getenv("GOOD_NEWS_SCHEDULER_INVOKER"),
            oidc_audience=os.getenv("GOOD_NEWS_OIDC_AUDIENCE"),
            observability_grafana_origin=os.getenv("GOOD_NEWS_OBSERVABILITY_GRAFANA_ORIGIN"),
            observability_grafana_host=os.getenv("GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST", "127.0.0.1"),
            observability_grafana_host_port=_read_int_env("GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT", 3000),
            observability_daily_report_time=os.getenv("GOOD_NEWS_OBSERVABILITY_DAILY_REPORT_TIME", "18:00"),
        )

    def _resolve_secret(
        self,
        env_var_name: str,
        secret_name: str,
        secret_store: SecretStore | None = None,
    ) -> str:
        value = os.getenv(env_var_name)
        if value:
            return value
        if secret_store is not None:
            try:
                return secret_store.get_secret(secret_name)
            except SecretNotFoundError as exc:
                raise MissingSecretError(
                    f"Missing secret {secret_name}; load it into {env_var_name} or provide a secret store."
                ) from exc
        raise MissingSecretError(
            f"Missing secret {secret_name}; load it into {env_var_name} or provide a secret store."
        )

    def app_master_key(self, secret_store: SecretStore | None = None) -> str:
        return self._resolve_secret(
            self.app_master_key_env_var,
            APP_MASTER_KEY_SECRET_NAME,
            secret_store,
        )

    def postgres_password(self, secret_store: SecretStore | None = None) -> str:
        return self._resolve_secret(
            self.postgres_password_env_var,
            POSTGRES_PASSWORD_SECRET_NAME,
            secret_store,
        )

    def database_url(self, secret_store: SecretStore | None = None) -> str:
        if self.database_url_override:
            return self.database_url_override
        password = quote_plus(self.postgres_password(secret_store))
        return (
            f"postgresql+psycopg://{quote_plus(self.postgres_user)}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )

    def gemini_api_key(self) -> str:
        value = os.getenv(self.gemini_api_key_env_var)
        if value:
            return value
        raise MissingSecretError(
            f"Missing Gemini API key; set {self.gemini_api_key_env_var}."
        )

    def allowed_email_set(self) -> frozenset[str]:
        return frozenset(
            email.strip().lower()
            for email in self.allowed_emails.split(",")
            if email.strip()
        )

    def analysis_service_base_url(self) -> str:
        return f"http://{self.analysis_service_host}:{self.analysis_service_port}"

    def content_api_service_base_url(self) -> str:
        return f"http://{self.content_api_service_host}:{self.content_api_service_port}"

    def _required_public_origin(self, *, value: str | None, env_var_name: str) -> str:
        normalized = (value or "").strip().rstrip("/")
        if normalized:
            return normalized
        raise MissingPublicOriginError(
            f"Missing public origin contract {env_var_name}; set it explicitly for user-facing absolute URLs."
        )

    def content_api_public_origin_url(self) -> str:
        return self._required_public_origin(
            value=self.public_content_api_origin,
            env_var_name="GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN",
        )

    def frontend_public_origin_url(self) -> str:
        return self._required_public_origin(
            value=self.public_frontend_origin,
            env_var_name="GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN",
        )

    def source_ingestion_service_base_url(self) -> str:
        return f"http://{self.source_ingestion_service_host}:{self.source_ingestion_service_port}"

    def delivery_service_base_url(self) -> str:
        return f"http://{self.delivery_service_host}:{self.delivery_service_port}"

    def observability_grafana_base_url(self) -> str:
        normalized = (self.observability_grafana_origin or "").strip().rstrip("/")
        if normalized:
            return normalized
        return f"http://{self.observability_grafana_host}:{self.observability_grafana_host_port}"

    def observability_dashboard_url(self) -> str:
        return (
            f"{self.observability_grafana_base_url()}"
            "/d/good-news-overview/good-news-observability-overview"
        )
