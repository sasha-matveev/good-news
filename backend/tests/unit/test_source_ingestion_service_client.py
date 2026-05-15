from __future__ import annotations

import httpx

from app.core.config import Settings
from app.schemas.source import SourceResponse
from app.services.ingestion_boundary import SourceOnboardingCommand
from app.services.source_ingestion_service_client import SourceIngestionServiceClient


def test_source_ingestion_service_client_posts_onboarding_command() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "id": 3,
                "display_name": "Example",
                "original_url": "https://example.com",
                "feed_url": "https://example.com/feed.xml",
                "strategy_kind": "feed",
                "active": True,
                "status": "ready",
                "last_success_at": None,
                "last_failure_at": None,
                "needs_readaptation": False,
                "readaptation_reason": None,
            },
        )

    client = SourceIngestionServiceClient(
        settings=Settings(source_ingestion_service_host="source-ingestion-service", source_ingestion_service_port=8200),
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    response = client.onboard_source(SourceOnboardingCommand(url="example.com"))

    assert captured["url"] == "http://source-ingestion-service:8200/internal/ingestion/onboarding-commands"
    assert captured["body"] == '{"url":"example.com"}'
    assert response == SourceResponse(
        id=3,
        display_name="Example",
        original_url="https://example.com",
        feed_url="https://example.com/feed.xml",
        strategy_kind="feed",
        active=True,
        status="ready",
        last_success_at=None,
        last_failure_at=None,
        needs_readaptation=False,
        readaptation_reason=None,
    )


def test_source_ingestion_service_client_triggers_run_once_sync() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"processed_source_ids": [1, 2]})

    client = SourceIngestionServiceClient(
        settings=Settings(source_ingestion_service_host="source-ingestion-service", source_ingestion_service_port=8200),
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    processed_source_ids = client.run_sync_once()

    assert captured["url"] == "http://source-ingestion-service:8200/internal/ingestion/sync/run-once"
    assert processed_source_ids == [1, 2]


def test_source_ingestion_service_client_uses_extended_timeout_for_sync() -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def post(self, url: str, timeout: object | None = None) -> httpx.Response:
            captured["url"] = url
            captured["timeout"] = timeout
            return httpx.Response(
                200,
                json={"processed_source_ids": [21]},
                request=httpx.Request("POST", url),
            )

    client = SourceIngestionServiceClient(
        settings=Settings(source_ingestion_service_host="source-ingestion-service", source_ingestion_service_port=8200),
        client=FakeClient(),
    )

    processed_source_ids = client.run_sync_once()

    assert captured["url"] == "http://source-ingestion-service:8200/internal/ingestion/sync/run-once"
    assert captured["timeout"] == 900.0
    assert processed_source_ids == [21]
