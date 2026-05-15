from __future__ import annotations

from dataclasses import asdict

import httpx

from app.core.config import Settings
from app.schemas.source import SourceResponse
from app.services.ingestion_boundary import SourceOnboardingCommand


class DuplicateSourceError(RuntimeError):
    pass


SYNC_RUN_ONCE_TIMEOUT_SECONDS = 900.0


class SourceIngestionServiceClient:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.client = client or httpx.Client(timeout=60.0)

    def onboard_source(self, command: SourceOnboardingCommand) -> SourceResponse:
        response = self.client.post(
            f"{self.settings.source_ingestion_service_base_url()}/internal/ingestion/onboarding-commands",
            json=asdict(command),
        )
        if response.status_code == 409:
            detail = response.json().get("detail", "Duplicate source.")
            raise DuplicateSourceError(detail)
        response.raise_for_status()
        return SourceResponse.model_validate(response.json())

    def run_sync_once(self) -> list[int]:
        response = self.client.post(
            f"{self.settings.source_ingestion_service_base_url()}/internal/ingestion/sync/run-once",
            timeout=SYNC_RUN_ONCE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return list(response.json()["processed_source_ids"])
