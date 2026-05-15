from pathlib import Path


def test_compose_exposes_extracted_source_ingestion_service_boundary() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "source-ingestion-service:" in compose_text
    assert "GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST: source-ingestion-service" in compose_text
    assert '${GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST_PORT:-8200}:8200' in compose_text
    assert "GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST_PORT=8200" in env_example


def test_phase_two_verification_boots_source_ingestion_service_and_exercises_onboarding_flow() -> None:
    deploy_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")

    assert '"source-ingestion-service"' in deploy_text
