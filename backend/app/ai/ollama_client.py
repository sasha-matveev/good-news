from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class OllamaAnalysisPayload:
    summary_ru: str
    topics: list[str]
    format: str
    technical_depth: str
    verdict: str
    verdict_reason: str


class OllamaClient:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.client = client or httpx.Client(timeout=60.0)

    def analyze_article(self, title: str, content: str) -> OllamaAnalysisPayload:
        prompt = (
            "Return strict JSON with keys summary_ru, topics, format, technical_depth, "
            "verdict, verdict_reason. Summary must be in Russian. "
            "verdict must be exactly one of: interesting, not_interesting. "
            f"Title: {title}\nContent: {content}"
        )
        response = self.client.post(
            f"{self.settings.ollama_base_url()}/api/generate",
            json={
                "model": self.settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        raw_payload = response.json()
        parsed = json.loads(raw_payload["response"])
        return _normalize_analysis_payload(parsed)


_VALID_VERDICTS = {"interesting", "not_interesting"}


def _normalize_analysis_payload(parsed: object) -> OllamaAnalysisPayload:
    if not isinstance(parsed, dict):
        raise TypeError("Ollama response payload must be a JSON object.")

    try:
        summary_value = parsed["summary_ru"] if "summary_ru" in parsed else parsed["summary"]
        coerced_verdict = _coerce_scalar_to_string(parsed["verdict"], field_name="verdict")
        normalized_verdict = coerced_verdict if coerced_verdict in _VALID_VERDICTS else ""
        return OllamaAnalysisPayload(
            summary_ru=_coerce_scalar_to_string(summary_value, field_name="summary_ru"),
            topics=_coerce_topics(parsed["topics"]),
            format=_coerce_scalar_to_string(parsed["format"], field_name="format"),
            technical_depth=_coerce_scalar_to_string(parsed["technical_depth"], field_name="technical_depth"),
            verdict=normalized_verdict,
            verdict_reason=_coerce_scalar_to_string(parsed["verdict_reason"], field_name="verdict_reason"),
        )
    except KeyError as exc:
        raise TypeError(f"Ollama response missing required field: {exc}") from exc


def _coerce_topics(value: object) -> list[str]:
    if isinstance(value, list):
        return [_normalize_value_to_contract_string(item, field_name="topics") for item in value]
    return [_normalize_value_to_contract_string(value, field_name="topics")]


def _coerce_scalar_to_string(value: object, *, field_name: str) -> str:
    return _normalize_value_to_contract_string(value, field_name=field_name)


def _normalize_value_to_contract_string(value: object, *, field_name: str) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        raise TypeError(
            f"Ollama field '{field_name}' must be JSON-serializable into the internal string contract."
        ) from exc
