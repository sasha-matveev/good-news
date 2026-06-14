from __future__ import annotations

from dataclasses import asdict

import httpx

from app.core.config import Settings
from app.services.analysis import AnalysisRequest, AnalysisResult


class AnalysisServiceClient:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.client = client or httpx.Client(timeout=60.0)

    def analyze_and_persist(self, request: AnalysisRequest) -> AnalysisResult:
        response = self.client.post(
            f"{self.settings.analysis_service_base_url()}/internal/analysis/requests",
            json=asdict(request),
        )
        response.raise_for_status()
        payload = response.json()
        return AnalysisResult(
            summary_ru=payload["summary_ru"],
            topics=list(payload["topics"]),
            format=payload["format"],
            technical_depth=payload["technical_depth"],
            verdict=payload["verdict"],
            verdict_reason=payload["verdict_reason"],
            relevance_score=int(payload.get("relevance_score", 0)),
        )
