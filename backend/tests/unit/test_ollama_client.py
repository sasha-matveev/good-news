from __future__ import annotations

import json

import httpx

from app.ai.ollama_client import OllamaClient
from app.core.config import Settings


def test_ollama_client_accepts_summary_alias_when_summary_ru_missing() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "summary": "Краткое резюме на русском языке.",
                        "topics": ["verification"],
                        "format": "article",
                        "technical_depth": "medium",
                        "verdict": "interesting",
                        "verdict_reason": "Useful boundary check.",
                    }
                )
            },
        )

    client = OllamaClient(
        settings=Settings(ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.analyze_article(title="Alpha", content="Body")

    assert captured == {
        "url": "http://ollama:11434/api/generate",
        "body": {
            "model": "llama3.2",
            "prompt": (
                "You are a JSON-only API. Read the article and return ONE JSON object. "
                "No explanation, no markdown.\n"
                "\n"
                "JSON fields:\n"
                '  "summary_ru": 1-2 sentences in Russian (Кириллица). '
                "Use only Russian words — no Latin, no code, no transliteration. "
                'If you cannot write proper Russian, use "".\n'
                '  "verdict_reason": 1 sentence in ENGLISH explaining why a developer '
                "would or would not want to read this. MUST be in English. No Russian.\n"
                '  "verdict": "interesting" if worth reading for a developer, '
                'otherwise "not_interesting".\n'
                '  "topics": array of 1-3 short English tags like ["AI", '
                '"performance", "testing"].\n'
                '  "format": one of tutorial|opinion|news|case-study|announcement|other.\n'
                '  "technical_depth": one of beginner|intermediate|advanced.\n'
                "\n"
                "Title: Alpha\n"
                "Content: Body"
            ),
            "stream": False,
            "format": "json",
        },
    }
    assert result.summary_ru == "Краткое резюме на русском языке."
    assert result.topics == ["verification"]
    assert result.format == "article"
    assert result.technical_depth == "medium"
    assert result.verdict == "interesting"
    assert result.verdict_reason == "Useful boundary check."


def test_ollama_client_normalizes_aliases_and_scalar_field_types() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "summary": 42,
                        "topics": "verification",
                        "format": 7,
                        "technical_depth": 3,
                        "verdict": True,
                        "verdict_reason": 9.5,
                    }
                )
            },
        )

    client = OllamaClient(
        settings=Settings(ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.analyze_article(title="Alpha", content="Body")

    assert result.summary_ru == "42"
    assert result.topics == ["verification"]
    assert result.format == ""  # "7" is not a valid format value → normalized to ""
    assert result.technical_depth == ""  # "3" is not a valid depth value → normalized to ""
    assert result.verdict == ""
    assert result.verdict_reason == "9.5"


def test_ollama_client_normalizes_nested_json_values_into_contract_strings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "summary_ru": {"text": "Short Russian summary.", "length": 2},
                        "topics": [{"name": "verification"}, ["runtime", 2], None],
                        "format": {"kind": "article", "score": 7},
                        "technical_depth": ["medium", {"level": 3}],
                        "verdict": {"label": "interesting", "confidence": 0.9},
                        "verdict_reason": ["Useful boundary check.", {"source": "runtime"}],
                    }
                )
            },
        )

    client = OllamaClient(
        settings=Settings(ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.analyze_article(title="Alpha", content="Body")

    assert result.summary_ru == ""  # JSON string has no Cyrillic → discarded by _is_mostly_cyrillic
    assert result.topics == ['{"name":"verification"}', '["runtime",2]', ""]
    assert result.format == ""  # JSON string is not a valid format value → normalized to ""
    assert result.technical_depth == ""  # JSON string is not a valid depth value → normalized to ""
    assert result.verdict == ""  # dict verdict is not a valid verdict string → normalized to ""
    assert result.verdict_reason == '["Useful boundary check.",{"source":"runtime"}]'


def test_ollama_client_normalizes_none_format_and_depth_to_empty_string() -> None:
    """GOO-50: None returned by LLM for format/technical_depth must be stored as '' not 'null'."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "summary_ru": "Summary text.",
                        "topics": ["devops"],
                        "format": None,
                        "technical_depth": None,
                        "verdict": "interesting",
                        "verdict_reason": "Good content.",
                    }
                )
            },
        )

    client = OllamaClient(
        settings=Settings(ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.analyze_article(title="Alpha", content="Body")

    assert result.format == "", f"Expected '' for None format, got {result.format!r}"
    assert result.technical_depth == "", f"Expected '' for None technical_depth, got {result.technical_depth!r}"


def test_ollama_client_normalizes_invalid_verdict_to_empty_string() -> None:
    """GOO-46: verdict values not in {interesting, not_interesting} must be normalized to ''."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "summary_ru": "Summary text.",
                        "topics": ["devops"],
                        "format": "article",
                        "technical_depth": "medium",
                        "verdict": "maybe",
                        "verdict_reason": "Not sure.",
                    }
                )
            },
        )

    client = OllamaClient(
        settings=Settings(ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.analyze_article(title="Alpha", content="Body")

    assert result.verdict == "", f"Expected '' for invalid verdict 'maybe', got {result.verdict!r}"


def test_ollama_client_wraps_non_list_topics_variants_into_single_item_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "summary_ru": "Short Russian summary.",
                        "topics": {"name": "verification", "confidence": 0.9},
                        "format": "article",
                        "technical_depth": "medium",
                        "verdict": "interesting",
                        "verdict_reason": {"detail": "Useful boundary check."},
                    }
                )
            },
        )

    client = OllamaClient(
        settings=Settings(ollama_host="ollama", ollama_port=11434, ollama_model="llama3.2"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.analyze_article(title="Alpha", content="Body")

    assert result.topics == ['{"confidence":0.9,"name":"verification"}']
    assert result.verdict_reason == '{"detail":"Useful boundary check."}'
