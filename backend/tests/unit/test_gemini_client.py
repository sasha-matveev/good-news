from __future__ import annotations

import json
import os

import httpx

from app.ai.gemini_client import (
    DEFAULT_SUMMARY_INSTRUCTIONS,
    DEFAULT_VERDICT_REASON_INSTRUCTIONS,
    ArticleInput,
    GeminiClient,
    build_json_fields_spec,
)
from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.setting import Setting
from app.testing.schema import stamp_schema_head


def _gemini_response(payload: object) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(payload)}]}}
        ]
    }


def _build_client(handler) -> GeminiClient:
    return GeminiClient(
        # High RPM keeps the throttle from sleeping between calls in tests.
        settings=Settings(gemini_model="gemini-2.5-flash-lite", gemini_max_rpm=60000),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_gemini_client_sends_json_request_and_accepts_summary_alias() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key_header"] = request.headers.get("x-goog-api-key")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary": "Краткое резюме на русском языке.",
                    "topics": ["verification"],
                    "format": "news",
                    "technical_depth": "intermediate",
                    "verdict": "interesting",
                    "verdict_reason": "Useful boundary check.",
                    "relevance_score": 8,
                }
            ),
        )

    import os

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        client = _build_client(handler)
        result = client.analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    )
    assert captured["api_key_header"] == "test-key"
    body = captured["body"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    prompt_text = body["contents"][0]["parts"][0]["text"]
    assert "Title: Alpha" in prompt_text
    assert "Content: Body" in prompt_text
    assert '"summary_ru"' in prompt_text
    assert '"relevance_score"' in prompt_text
    # The summary must be requested as a detailed, multi-sentence Russian overview,
    # not a one-line restatement of the title.
    assert "detailed summary in Russian" in prompt_text
    assert "4-6 sentences" in prompt_text
    # No session factory → no feedback profile → no preference block in the prompt.
    assert "READER PREFERENCE PROFILE" not in prompt_text

    assert result.summary_ru == "Краткое резюме на русском языке."
    assert result.topics == ["verification"]
    assert result.format == "news"
    assert result.technical_depth == "intermediate"
    assert result.verdict == "interesting"
    assert result.verdict_reason == "Useful boundary check."
    assert result.relevance_score == 8


def test_gemini_client_normalizes_aliases_and_scalar_field_types() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary": 42,
                    "topics": "verification",
                    "format": 7,
                    "technical_depth": 3,
                    "verdict": True,
                    "verdict_reason": 9.5,
                }
            ),
        )

    import os

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        result = _build_client(handler).analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    assert result.summary_ru == "42"
    assert result.topics == ["verification"]
    assert result.format == ""  # "7" is not a valid format value → normalized to ""
    assert result.technical_depth == ""  # "3" is not a valid depth value → normalized to ""
    assert result.verdict == ""
    assert result.verdict_reason == "9.5"


def test_gemini_client_normalizes_nested_json_values_into_contract_strings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": {"text": "Short Russian summary.", "length": 2},
                    "topics": [{"name": "verification"}, ["runtime", 2], None],
                    "format": {"kind": "article", "score": 7},
                    "technical_depth": ["medium", {"level": 3}],
                    "verdict": {"label": "interesting", "confidence": 0.9},
                    "verdict_reason": ["Useful boundary check.", {"source": "runtime"}],
                }
            ),
        )

    import os

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        result = _build_client(handler).analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    assert result.summary_ru == ""  # JSON string has no Cyrillic → discarded by _is_mostly_cyrillic
    assert result.topics == ['{"name":"verification"}', '["runtime",2]', ""]
    assert result.format == ""  # JSON string is not a valid format value → normalized to ""
    assert result.technical_depth == ""  # JSON string is not a valid depth value → normalized to ""
    assert result.verdict == ""  # dict verdict is not a valid verdict string → normalized to ""
    assert result.verdict_reason == '["Useful boundary check.",{"source":"runtime"}]'


def test_gemini_client_normalizes_none_format_and_depth_to_empty_string() -> None:
    """GOO-50: None returned by LLM for format/technical_depth must be stored as '' not 'null'."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": "Summary text.",
                    "topics": ["devops"],
                    "format": None,
                    "technical_depth": None,
                    "verdict": "interesting",
                    "verdict_reason": "Good content.",
                }
            ),
        )

    import os

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        result = _build_client(handler).analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    assert result.format == "", f"Expected '' for None format, got {result.format!r}"
    assert result.technical_depth == "", f"Expected '' for None technical_depth, got {result.technical_depth!r}"


def test_gemini_client_normalizes_invalid_verdict_to_empty_string() -> None:
    """GOO-46: verdict values not in {interesting, not_interesting} must be normalized to ''."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": "Summary text.",
                    "topics": ["devops"],
                    "format": "article",
                    "technical_depth": "medium",
                    "verdict": "maybe",
                    "verdict_reason": "Not sure.",
                }
            ),
        )

    import os

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        result = _build_client(handler).analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    assert result.verdict == "", f"Expected '' for invalid verdict 'maybe', got {result.verdict!r}"


def test_gemini_client_wraps_non_list_topics_variants_into_single_item_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": "Short Russian summary.",
                    "topics": {"name": "verification", "confidence": 0.9},
                    "format": "article",
                    "technical_depth": "medium",
                    "verdict": "interesting",
                    "verdict_reason": {"detail": "Useful boundary check."},
                }
            ),
        )

    import os

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        result = _build_client(handler).analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    assert result.topics == ['{"confidence":0.9,"name":"verification"}']
    assert result.verdict_reason == '{"detail":"Useful boundary check."}'


def _batch_item(article_id: int) -> dict:
    return {
        "id": article_id,
        "summary_ru": "Краткое резюме на русском языке.",
        "topics": ["ai"],
        "format": "news",
        "technical_depth": "intermediate",
        "verdict": "interesting",
        "verdict_reason": "Useful.",
        "relevance_score": 7,
    }


def test_gemini_client_batches_articles_into_single_request() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json=_gemini_response({"results": [_batch_item(1), _batch_item(2), _batch_item(3)]}),
        )

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        client = _build_client(handler)
        results = client.analyze_articles(
            [
                ArticleInput(post_id=1, title="A", content="a"),
                ArticleInput(post_id=2, title="B", content="b"),
                ArticleInput(post_id=3, title="C", content="c"),
            ]
        )
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    # Three articles, one HTTP request (default batch size 10).
    assert len(calls) == 1
    prompt = calls[0]["contents"][0]["parts"][0]["text"]
    assert "[id=1]" in prompt and "[id=2]" in prompt and "[id=3]" in prompt
    assert '"results"' in prompt
    assert set(results.keys()) == {1, 2, 3}
    assert results[1].verdict == "interesting"
    assert results[1].relevance_score == 7
    assert results[2].summary_ru == "Краткое резюме на русском языке."


def test_gemini_client_batch_omits_ids_missing_from_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Model returns only id 1 and a stray unexpected id 99.
        return httpx.Response(
            200,
            json=_gemini_response({"results": [_batch_item(1), _batch_item(99)]}),
        )

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        results = _build_client(handler).analyze_articles(
            [
                ArticleInput(post_id=1, title="A", content="a"),
                ArticleInput(post_id=2, title="B", content="b"),
            ]
        )
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    # id 2 missing → not in results; stray id 99 ignored (not requested).
    assert set(results.keys()) == {1}


def test_gemini_client_retries_on_429(monkeypatch) -> None:
    monkeypatch.setattr("app.ai.gemini_client.time.sleep", lambda _seconds: None)
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": "Резюме.",
                    "topics": ["ai"],
                    "format": "news",
                    "technical_depth": "intermediate",
                    "verdict": "interesting",
                    "verdict_reason": "Useful.",
                }
            ),
        )

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        result = _build_client(handler).analyze_article(title="A", content="a")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    assert len(attempts) == 2  # one 429, one success
    assert result.verdict == "interesting"


def test_build_json_fields_spec_injects_custom_instructions_and_keeps_fixed_lines() -> None:
    spec = build_json_fields_spec("MY CUSTOM SUMMARY GUIDE", "MY CUSTOM VERDICT GUIDE")

    # Editable instruction texts are injected for their respective fields.
    assert '"summary_ru": MY CUSTOM SUMMARY GUIDE' in spec
    assert '"verdict_reason": MY CUSTOM VERDICT GUIDE' in spec
    # The fixed JSON contract lines remain unchanged.
    assert '"verdict": "interesting" if worth reading for this reader' in spec
    assert '"relevance_score": integer 0-10' in spec
    assert '"topics": array of 1-3 short English tags' in spec
    assert '"format": one of tutorial|opinion|news|case-study|announcement|other.' in spec
    assert '"technical_depth": one of beginner|intermediate|advanced.' in spec


def test_gemini_client_without_session_factory_uses_default_summary_instructions() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": "Резюме.",
                    "topics": ["ai"],
                    "format": "news",
                    "technical_depth": "intermediate",
                    "verdict": "interesting",
                    "verdict_reason": "Useful.",
                }
            ),
        )

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        # _build_client constructs the client WITHOUT a session_factory.
        _build_client(handler).analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    prompt_text = captured["body"]["contents"][0]["parts"][0]["text"]
    assert "4-6 sentences" in prompt_text
    assert DEFAULT_SUMMARY_INSTRUCTIONS in prompt_text
    assert DEFAULT_VERDICT_REASON_INSTRUCTIONS in prompt_text


def test_gemini_client_uses_custom_prompt_from_database() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    custom_summary = "Дай однострочное резюме на русском."
    with session_scope(session_factory) as session:
        session.add(Setting(key="analysis_summary_prompt", value=custom_summary))
        session.commit()

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": "Резюме.",
                    "topics": ["ai"],
                    "format": "news",
                    "technical_depth": "intermediate",
                    "verdict": "interesting",
                    "verdict_reason": "Useful.",
                }
            ),
        )

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        client = GeminiClient(
            settings=Settings(gemini_model="gemini-2.5-flash-lite", gemini_max_rpm=60000),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            session_factory=session_factory,
        )
        client.analyze_article(title="Alpha", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    prompt_text = captured["body"]["contents"][0]["parts"][0]["text"]
    assert custom_summary in prompt_text
    # The unset verdict_reason prompt still falls back to its default.
    assert DEFAULT_VERDICT_REASON_INSTRUCTIONS in prompt_text


def test_gemini_client_injects_reader_preference_profile_into_prompt() -> None:
    from datetime import UTC, datetime

    from app.models.feedback import Feedback
    from app.models.post import Post
    from app.models.post_analysis import PostAnalysis
    from app.models.source import Source

    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    stamp_schema_head(session_factory)

    # Seed one "interesting" reaction so build_preference_profile yields signals.
    with session_scope(session_factory) as session:
        session.add(Source(id=1, display_name="Alpha Blog", original_url="https://alpha.example", status="ready"))
        session.add(
            Post(
                id=1,
                source_id=1,
                canonical_url="https://alpha.example/posts/one",
                title="Liked post",
                published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
                raw_content="content",
                content_hash="hash-1",
                ingest_metadata='{"strategy":"feed"}',
            )
        )
        session.add(
            PostAnalysis(
                post_id=1,
                summary_ru="s",
                metadata_json=json.dumps(
                    {"topics": ["observability"], "format": "postmortem", "technical_depth": "deep"},
                    sort_keys=True,
                ),
            )
        )
        session.add(Feedback(post_id=1, state="interesting"))
        session.commit()

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json=_gemini_response(
                {
                    "summary_ru": "Резюме.",
                    "topics": ["ai"],
                    "format": "news",
                    "technical_depth": "intermediate",
                    "verdict": "interesting",
                    "verdict_reason": "Useful.",
                    "relevance_score": 6,
                }
            ),
        )

    os.environ["GOOD_NEWS_GEMINI_API_KEY"] = "test-key"
    try:
        client = GeminiClient(
            settings=Settings(gemini_model="gemini-2.5-flash-lite", gemini_max_rpm=60000),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            session_factory=session_factory,
        )
        client.analyze_article(title="New post", content="Body")
    finally:
        del os.environ["GOOD_NEWS_GEMINI_API_KEY"]

    prompt_text = captured["body"]["contents"][0]["parts"][0]["text"]
    assert "READER PREFERENCE PROFILE" in prompt_text
    # The reader's positive signals (liked source + topic) surface in the prompt.
    assert "Alpha Blog" in prompt_text
    assert "observability" in prompt_text
