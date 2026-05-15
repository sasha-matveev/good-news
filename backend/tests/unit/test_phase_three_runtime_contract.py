from pathlib import Path


def test_compose_exposes_app_with_analysis_stub_support() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "app:" in compose_text
    assert "GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON" in compose_text
    assert "GOOD_NEWS_ANALYSIS_SERVICE_HOST_PORT=8100" in env_example


def test_task_six_acceptance_uses_stub_response_config() -> None:
    deploy_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")

    assert "GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON" in deploy_text
