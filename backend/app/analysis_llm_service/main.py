from __future__ import annotations

import json
from collections.abc import Callable, Generator

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.gemini_client import GeminiClient
from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.core.backend_identity import install_backend_identity
from app.core.schema_guard import assert_database_schema_is_current
from app.models.post import Post
from app.services.analysis import AnalysisRequest, AnalysisResult, analyze_request, persist_analysis_result


class AnalysisRequestBody(BaseModel):
    post_id: int
    title: str
    content: str


class AnalysisResponseBody(BaseModel):
    summary_ru: str
    topics: list[str]
    format: str
    technical_depth: str
    verdict: str
    verdict_reason: str
    relevance_score: int = 0


def _stub_result_from_settings(settings: Settings) -> AnalysisResult | None:
    if not settings.analysis_stub_response_json:
        return None
    payload = json.loads(settings.analysis_stub_response_json)
    return AnalysisResult(
        summary_ru=payload["summary_ru"],
        topics=list(payload["topics"]),
        format=payload["format"],
        technical_depth=payload["technical_depth"],
        verdict=payload["verdict"],
        verdict_reason=payload["verdict_reason"],
        relevance_score=int(payload.get("relevance_score", 0)),
    )


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    analysis_client_factory: Callable[[], object] | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    app = FastAPI(title="Good News Analysis LLM Service")
    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.analysis_stub_result = _stub_result_from_settings(resolved_settings)
    app.state.analysis_client_factory = analysis_client_factory or (lambda: GeminiClient(settings=resolved_settings))
    install_backend_identity(app)

    @app.on_event("startup")
    def ensure_session_factory() -> None:
        if app.state.session_factory is None:
            engine = create_engine_from_settings(settings=resolved_settings)
            app.state.session_factory = create_session_factory(engine)
        assert_database_schema_is_current(app.state.session_factory)

    def get_session_factory(request: Request) -> sessionmaker[Session]:
        return request.app.state.session_factory

    def get_session(
        session_factory: sessionmaker[Session] = Depends(get_session_factory),
    ) -> Generator[Session, None, None]:
        with session_scope(session_factory) as session:
            yield session

    @app.get("/health")
    def health(session: Session = Depends(get_session)) -> dict[str, str]:
        session.execute(select(1))
        return {"status": "ok"}

    @app.post("/internal/analysis/requests", response_model=AnalysisResponseBody)
    def analyze_and_persist_request(
        payload: AnalysisRequestBody,
        request: Request,
        session: Session = Depends(get_session),
    ) -> AnalysisResponseBody:
        analysis_request = AnalysisRequest(
            post_id=payload.post_id,
            title=payload.title,
            content=payload.content,
        )
        result = request.app.state.analysis_stub_result
        if result is None:
            result = analyze_request(
                analysis_request,
                analysis_client=request.app.state.analysis_client_factory(),
            )
        persist_analysis_result(
            session=session,
            request=analysis_request,
            result=result,
        )
        # Commit before returning so downstream readers in other runtimes observe the write deterministically.
        session.commit()
        return AnalysisResponseBody(
            summary_ru=result.summary_ru,
            topics=result.topics,
            format=result.format,
            technical_depth=result.technical_depth,
            verdict=result.verdict,
            verdict_reason=result.verdict_reason,
            relevance_score=result.relevance_score,
        )

    return app


app = create_app()
