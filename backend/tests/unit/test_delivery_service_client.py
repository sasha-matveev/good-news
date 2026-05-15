from __future__ import annotations

import httpx

from app.core.config import Settings
from app.services.delivery_service_client import DeliveryServiceClient


def test_delivery_service_client_posts_test_email_command() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "sent"})

    client = DeliveryServiceClient(
        settings=Settings(delivery_service_host="delivery-service", delivery_service_port=8300),
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    response = client.send_test_email()

    assert captured["url"] == "http://delivery-service:8300/internal/delivery/test-email"
    assert response == {"status": "sent"}


def test_delivery_service_client_posts_run_once_command() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"digest_id": 4, "status": "sent", "delivered": True, "item_count": 1})

    client = DeliveryServiceClient(
        settings=Settings(delivery_service_host="delivery-service", delivery_service_port=8300),
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    response = client.run_daily_digest_once()

    assert captured["url"] == "http://delivery-service:8300/internal/delivery/digests/run-once"
    assert response == {"digest_id": 4, "status": "sent", "delivered": True, "item_count": 1}
