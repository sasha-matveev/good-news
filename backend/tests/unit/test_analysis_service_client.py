from __future__ import annotations

import json

import httpx

from app.core.config import Settings
from app.services.analysis import AnalysisRequest
from app.services.analysis_service_client import AnalysisServiceClient


def test_analysis_service_client_posts_explicit_contract_and_parses_result() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "summary_ru": "Short Russian summary.",
                "topics": ["verification"],
                "format": "article",
                "technical_depth": "medium",
                "verdict": "interesting",
                "verdict_reason": "Useful boundary check.",
            },
        )

    client = AnalysisServiceClient(
        settings=Settings(analysis_service_host="analysis-llm-service", analysis_service_port=8100),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.analyze_and_persist(
        AnalysisRequest(post_id=11, title="Alpha", content="Body"),
    )

    assert captured == {
        "url": "http://analysis-llm-service:8100/internal/analysis/requests",
        "body": {
            "post_id": 11,
            "title": "Alpha",
            "content": "Body",
        },
    }
    assert result.summary_ru == "Short Russian summary."
    assert result.topics == ["verification"]
