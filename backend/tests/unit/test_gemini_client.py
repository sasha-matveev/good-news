from __future__ import annotations

import json
import os

import httpx

from app.ai.gemini_client import ArticleInput, GeminiClient
from app.core.config import Settings


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

    assert result.summary_ru == "Краткое резюме на русском языке."
    assert result.topics == ["verification"]
    assert result.format == "news"
    assert result.technical_depth == "intermediate"
    assert result.verdict == "interesting"
    assert result.verdict_reason == "Useful boundary check."


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
