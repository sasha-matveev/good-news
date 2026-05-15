from pathlib import Path


def test_compose_exposes_app_service_boundary() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "app:" in compose_text
    assert '${GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT:-8000}:8000' in compose_text
    assert "GOOD_NEWS_CONTENT_API_SERVICE_HOST=localhost" in env_example
    assert "GOOD_NEWS_CONTENT_API_SERVICE_PORT=8000" in env_example


def test_phase_two_verification_exercises_stable_frontend_contracts() -> None:
    acceptance_text = Path("scripts/validation/verify-phase2-isolated-acceptance.ps1").read_text(encoding="utf-8")
    integration_text = Path("scripts/validation/verify-phase2-integration.ps1").read_text(encoding="utf-8")

    assert '$env:GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT = Get-GoodNewsAvailableTcpPort' in acceptance_text
    assert "test_content_api_service_runtime.py" in integration_text
