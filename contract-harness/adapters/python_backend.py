from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from app.core.config import Settings
from app.core.db import session_scope
from app.main import create_app
from app.services.analysis import AnalysisRequest, AnalysisResult, persist_analysis_result


def _fixture(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing contract fixture {name}")
    return value


def _fixed_now() -> datetime:
    parsed = datetime.fromisoformat(_fixture("GOOD_NEWS_FIXED_NOW").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("GOOD_NEWS_FIXED_NOW must include a timezone.")
    return parsed.astimezone(UTC)


def _token_verifier():
    claims_by_token = json.loads(_fixture("GOOD_NEWS_CONTRACT_AUTH_TOKENS_JSON"))

    def verify(token: str) -> dict:
        claims = claims_by_token.get(token)
        if not isinstance(claims, dict):
            raise ValueError("Unknown contract token.")
        return claims

    return verify


def _analysis_result() -> AnalysisResult:
    payload = json.loads(_fixture("GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON"))
    return AnalysisResult(
        summary_ru=payload["summary_ru"],
        topics=list(payload["topics"]),
        format=payload["format"],
        technical_depth=payload["technical_depth"],
        verdict=payload["verdict"],
        verdict_reason=payload["verdict_reason"],
        relevance_score=int(payload["relevance_score"]),
    )


class ContractAnalysisClient:
    def __init__(self, session_factory, result: AnalysisResult) -> None:
        self._session_factory = session_factory
        self._result = result

    def analyze_and_persist(self, request: AnalysisRequest) -> AnalysisResult:
        with session_scope(self._session_factory) as session:
            persist_analysis_result(session=session, request=request, result=self._result)
        return self._result

    def analyze_and_persist_batch(self, requests: list[AnalysisRequest]) -> list[int]:
        with session_scope(self._session_factory) as session:
            for request in requests:
                persist_analysis_result(session=session, request=request, result=self._result)
        return []


settings = Settings.from_env()
analysis_result = _analysis_result()
app = create_app(
    settings=settings,
    now_provider=_fixed_now,
    analysis_client_factory=lambda: ContractAnalysisClient(app.state.session_factory, analysis_result),
)
verifier = _token_verifier()
app.state.user_token_verifier = verifier
app.state.scheduler_oidc_verifier = verifier
