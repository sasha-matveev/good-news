from pathlib import Path


def test_compose_exposes_app_with_ingestion_responses_support() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "app:" in compose_text
    assert "GOOD_NEWS_INGESTION_RESPONSES_JSON" in compose_text
    assert "GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST_PORT=8200" in env_example


def test_phase_two_verification_exercises_onboarding_flow() -> None:
    ingestion_test_text = Path("backend/tests/unit/test_source_ingestion_service_client.py").read_text(encoding="utf-8")

    assert "onboard_source" in ingestion_test_text
    assert "SourceOnboardingCommand" in ingestion_test_text
