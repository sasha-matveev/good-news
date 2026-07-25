from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.main import create_app
from app.services.analysis import AnalysisRequest, AnalysisResult
from app.services.stub_analysis_client import StubAnalysisClient


def test_monolith_selects_stub_client_when_response_is_configured() -> None:
    settings = Settings(
        analysis_stub_response_json=(
            '{"summary_ru":"Результат","topics":["platform"],"format":"article",'
            '"technical_depth":"medium","verdict":"interesting",'
            '"verdict_reason":"Useful.","relevance_score":8}'
        )
    )

    app = create_app(session_factory=MagicMock(), settings=settings)

    assert isinstance(app.state.analysis_client_factory(), StubAnalysisClient)


def test_batch_persists_every_request_with_configured_result() -> None:
    session = MagicMock()
    session_scope = MagicMock()
    session_scope.return_value.__enter__.return_value = session
    result = AnalysisResult(
        summary_ru="Результат",
        topics=["platform"],
        format="article",
        technical_depth="medium",
        verdict="interesting",
        verdict_reason="Useful.",
        relevance_score=8,
    )
    requests = [
        AnalysisRequest(post_id=1, title="One", content="First"),
        AnalysisRequest(post_id=2, title="Two", content="Second"),
    ]
    client = StubAnalysisClient(session_factory=MagicMock(), result=result)

    with (
        patch("app.services.stub_analysis_client.session_scope", session_scope),
        patch("app.services.stub_analysis_client.persist_analysis_result") as persist,
    ):
        failed = client.analyze_and_persist_batch(requests)

    assert failed == []
    assert [call.kwargs["request"] for call in persist.call_args_list] == requests
    assert all(call.kwargs["result"] == result for call in persist.call_args_list)
