from __future__ import annotations

import json

from app.models.post_analysis import PostAnalysis
from app.services.analysis import AnalysisResult, StoredPostAnalysis, analyze_post_payload


class FakeAnalysisClient:
    def __init__(self, result: AnalysisResult) -> None:
        self.result = result
        self.calls: list[dict[str, str]] = []

    def analyze_article(self, title: str, content: str) -> AnalysisResult:
        self.calls.append({"title": title, "content": content})
        return self.result


def test_analyze_post_payload_returns_russian_summary_and_structured_fields() -> None:
    client = FakeAnalysisClient(
        AnalysisResult(
            summary_ru="Короткое русское summary.",
            topics=["observability", "postgres"],
            format="tutorial",
            technical_depth="deep",
            verdict="interesting",
            verdict_reason="Strong practical backend content.",
        )
    )

    payload = analyze_post_payload(
        title="Deep Postgres observability",
        content="A long article about dashboards and database internals.",
        analysis_client=client,
    )

    assert payload["summary_ru"] == "Короткое русское summary."
    assert json.loads(payload["metadata_json"]) == {
        "topics": ["observability", "postgres"],
        "format": "tutorial",
        "technical_depth": "deep",
        "verdict": "interesting",
        "verdict_reason": "Strong practical backend content.",
    }
    assert client.calls == [
        {
            "title": "Deep Postgres observability",
            "content": "A long article about dashboards and database internals.",
        }
    ]


def test_stored_post_analysis_parses_analysis_owned_persistence_shape() -> None:
    stored = StoredPostAnalysis.from_persistence(
        summary_ru="Short Russian summary.",
        metadata_json=json.dumps(
            {
                "topics": ["observability"],
                "format": "postmortem",
                "technical_depth": "deep",
                "verdict": "interesting",
                "verdict_reason": "Clear backend learning value.",
            }
        ),
    )

    assert stored.summary_ru == "Short Russian summary."
    assert stored.topics == ["observability"]
    assert stored.format == "postmortem"
    assert stored.technical_depth == "deep"
    assert stored.verdict == "interesting"
    assert stored.verdict_reason == "Clear backend learning value."


def test_analysis_result_persists_through_analysis_owned_write_path() -> None:
    from app.core.db import create_engine_from_url, create_session_factory, session_scope
    from app.models.base import Base
    from app.services.analysis import AnalysisRequest, persist_analysis_result

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        persist_analysis_result(
            session=session,
            request=AnalysisRequest(post_id=11, title="Alpha", content="Body"),
            result=AnalysisResult(
                summary_ru="Short summary",
                topics=["postgres"],
                format="tutorial",
                technical_depth="deep",
                verdict="interesting",
                verdict_reason="Useful practical content.",
            ),
        )

    with session_scope(session_factory) as session:
        saved = session.query(PostAnalysis).filter(PostAnalysis.post_id == 11).one()

    assert saved.summary_ru == "Short summary"
    assert json.loads(saved.metadata_json) == {
        "topics": ["postgres"],
        "format": "tutorial",
        "technical_depth": "deep",
        "verdict": "interesting",
        "verdict_reason": "Useful practical content.",
    }
