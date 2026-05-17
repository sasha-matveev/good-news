from pathlib import Path


def test_docker_compose_requires_secret_env_vars_and_health_sequences_backend() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "${POSTGRES_PASSWORD:?" in compose_text
    assert "${GOOD_NEWS_POSTGRES_PASSWORD:?" in compose_text
    assert "${GOOD_NEWS_APP_MASTER_KEY:?" in compose_text
    assert "healthcheck:" in compose_text
    assert "pg_isready" in compose_text
    assert "condition: service_healthy" in compose_text


def test_readme_documents_secrets_setup() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert "GOOD_NEWS_APP_MASTER_KEY" in readme_text
    assert "GOOD_NEWS_POSTGRES_PASSWORD" in readme_text
    assert "load-dev-secrets.ps1" in readme_text
