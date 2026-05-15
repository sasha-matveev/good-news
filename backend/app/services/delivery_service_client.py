from __future__ import annotations

import httpx

from app.core.config import Settings


class DeliveryServiceClient:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.client = client or httpx.Client(timeout=60.0)

    def send_test_email(self) -> dict[str, str]:
        response = self.client.post(
            f"{self.settings.delivery_service_base_url()}/internal/delivery/test-email",
        )
        response.raise_for_status()
        payload = response.json()
        return {"status": payload["status"]}

    def run_daily_digest_once(self) -> dict[str, object]:
        response = self.client.post(
            f"{self.settings.delivery_service_base_url()}/internal/delivery/digests/run-once",
        )
        response.raise_for_status()
        return dict(response.json())
