from pathlib import Path


def test_compose_exposes_extracted_analysis_service_boundary() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "analysis-llm-service:" in compose_text
    assert "GOOD_NEWS_ANALYSIS_SERVICE_HOST: analysis-llm-service" in compose_text
    assert '${GOOD_NEWS_ANALYSIS_SERVICE_HOST_PORT:-8100}:8100' in compose_text
    assert "GOOD_NEWS_ANALYSIS_SERVICE_HOST_PORT=8100" in env_example


def test_task_six_acceptance_now_boots_analysis_service_and_uses_service_contract() -> None:
    deploy_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")

    assert '"analysis-llm-service"' in deploy_text
    assert "GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON" in deploy_text
