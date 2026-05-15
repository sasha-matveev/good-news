from pathlib import Path


def test_compose_exposes_extracted_delivery_service_boundary() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "delivery-service:" in compose_text
    assert "GOOD_NEWS_DELIVERY_SERVICE_HOST: delivery-service" in compose_text
    assert '${GOOD_NEWS_DELIVERY_SERVICE_HOST_PORT:-8300}:8300' in compose_text
    assert "GOOD_NEWS_DELIVERY_SERVICE_HOST=localhost" in env_example
    assert "GOOD_NEWS_DELIVERY_SERVICE_PORT=8300" in env_example


def test_phase_two_verification_boots_delivery_service_and_exercises_digest_delivery_flow() -> None:
    script_text = Path("scripts/validation/verify-task6-full-app.ps1").read_text(encoding="utf-8")
    acceptance_text = Path("scripts/validation/verify-phase2-isolated-acceptance.ps1").read_text(encoding="utf-8")
    integration_text = Path("scripts/validation/verify-phase2-integration.ps1").read_text(encoding="utf-8")

    assert '"delivery-service"' in script_text
    assert '$deliveryServiceBaseUrl = "http://127.0.0.1:$DeliveryServicePort"' in script_text
    assert "/internal/delivery/digests/run-once" in script_text
    assert '$env:GOOD_NEWS_DELIVERY_SERVICE_HOST_PORT = Get-GoodNewsAvailableTcpPort' in acceptance_text
    assert "test_delivery_service_runtime.py" in integration_text
