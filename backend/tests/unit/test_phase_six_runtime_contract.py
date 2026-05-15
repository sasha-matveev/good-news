from pathlib import Path


def test_compose_exposes_content_api_service_boundary() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "content-api-service:" in compose_text
    assert '${GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT:-8000}:8000' in compose_text
    assert "GOOD_NEWS_CONTENT_API_SERVICE_HOST=localhost" in env_example
    assert "GOOD_NEWS_CONTENT_API_SERVICE_PORT=8000" in env_example


def test_phase_two_verification_boots_content_api_service_and_exercises_stable_frontend_contracts() -> None:
    script_text = Path("scripts/validation/verify-task6-full-app.ps1").read_text(encoding="utf-8")
    acceptance_text = Path("scripts/validation/verify-phase2-isolated-acceptance.ps1").read_text(encoding="utf-8")
    integration_text = Path("scripts/validation/verify-phase2-integration.ps1").read_text(encoding="utf-8")

    assert '"content-api-service"' in script_text
    assert '$contentApiServiceBaseUrl = "http://127.0.0.1:$ContentApiServicePort"' in script_text
    assert "/api/posts?window=all" in script_text
    assert "/api/settings/test-email" in script_text
    assert '$env:GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT = Get-GoodNewsAvailableTcpPort' in acceptance_text
    assert "test_content_api_service_runtime.py" in integration_text
