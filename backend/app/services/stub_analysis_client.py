from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.services.analysis import AnalysisRequest, AnalysisResult, persist_analysis_result


class StubAnalysisClient:
    """Persist one configured deterministic result without crossing an external boundary."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        result: AnalysisResult,
    ) -> None:
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
