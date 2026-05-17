from pathlib import Path


def test_compose_exposes_app_with_smtp_support() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "app:" in compose_text
    assert '${GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT:-8000}:8000' in compose_text
    assert "GOOD_NEWS_DELIVERY_SERVICE_HOST=localhost" in env_example
    assert "GOOD_NEWS_DELIVERY_SERVICE_PORT=8300" in env_example


