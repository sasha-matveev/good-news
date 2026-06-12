from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from app.core.config import Settings

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker, Session
    from app.services.analysis import AnalysisRequest, AnalysisResult

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


@dataclass(frozen=True)
class GeminiAnalysisPayload:
    summary_ru: str
    topics: list[str]
    format: str
    technical_depth: str
    verdict: str
    verdict_reason: str


class GeminiClient:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        session_factory: "sessionmaker[Session] | None" = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.client = client or httpx.Client(timeout=60.0)
        self._session_factory = session_factory

    def analyze_and_persist(self, request: "AnalysisRequest") -> "AnalysisResult":
        """Implement the same interface as AnalysisServiceClient for the monolith path."""
        from app.core.db import session_scope
        from app.services.analysis import AnalysisResult, analyze_request, persist_analysis_result

        result = analyze_request(request, self)
        if self._session_factory is not None:
            with session_scope(self._session_factory) as session:
                persist_analysis_result(session=session, request=request, result=result)
                session.commit()
        return result

    def analyze_article(self, title: str, content: str) -> GeminiAnalysisPayload:
        content_snippet = content[:4000]
        prompt = (
            "You are a JSON-only API. Read the article and return ONE JSON object. No explanation, no markdown.\n"
            "\n"
            "JSON fields:\n"
            '  "summary_ru": 1-2 sentences in Russian (Кириллица). '
            "Use only Russian words — no Latin, no code, no transliteration. "
            'If you cannot write proper Russian, use "".\n'
            '  "verdict_reason": 1 sentence in ENGLISH explaining why a developer would or would not want to read this. '
            "MUST be in English. No Russian.\n"
            '  "verdict": "interesting" if worth reading for a developer, otherwise "not_interesting".\n'
            '  "topics": array of 1-3 short English tags like ["AI", "performance", "testing"].\n'
            '  "format": one of tutorial|opinion|news|case-study|announcement|other.\n'
            '  "technical_depth": one of beginner|intermediate|advanced.\n'
            "\n"
            f"Title: {title}\n"
            f"Content: {content_snippet}"
        )
        response = self.client.post(
            f"{GEMINI_API_BASE_URL}/models/{self.settings.gemini_model}:generateContent",
            headers={"x-goog-api-key": self.settings.gemini_api_key()},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2,
                },
            },
        )
        response.raise_for_status()
        raw_payload = response.json()
        try:
            text = raw_payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise TypeError(f"Gemini response missing candidate text: {exc}") from exc
        parsed = json.loads(text)
        return _normalize_analysis_payload(parsed)


_VALID_VERDICTS = {"interesting", "not_interesting"}
_VALID_FORMATS = {"tutorial", "opinion", "news", "case-study", "announcement", "other"}
_VALID_DEPTHS = {"beginner", "intermediate", "advanced"}

_SNAKE_CASE_RE = re.compile(r"\w+_\w+")


def _has_exotic_alphabet(text: str) -> bool:
    """Return True if *text* contains letter characters outside ASCII and Cyrillic.

    Devanagari, Arabic, CJK, etc. indicate a corrupted model output.
    Only Unicode Letter categories are checked — punctuation/symbols are ignored.
    """
    for c in text:
        if unicodedata.category(c).startswith("L"):
            code = ord(c)
            # Allow ASCII + Latin Extended A/B/IPA (U+0000–U+036F)
            # Allow Cyrillic block (U+0400–U+052F)
            if not (code <= 0x036F or 0x0400 <= code <= 0x052F):
                return True
    return False


def _is_mostly_cyrillic(text: str) -> bool:
    """Return True when the summary looks like valid Russian prose.

    Returns False (summary will be discarded) when:
    - Latin characters outnumber Cyrillic ones (transliteration / English garbage)
    - Any snake_case token is present (model wrote code-style identifiers)
    - Any letter from a non-Latin/non-Cyrillic script is present (Devanagari, CJK, …)

    Empty strings return True — an empty summary is valid (no analysis yet).
    """
    if not text:
        return True
    # Reject snake_case tokens — the model wrote code instead of prose
    if _SNAKE_CASE_RE.search(text):
        return False
    # Reject Devanagari, CJK, Arabic, etc. — those are corrupted outputs
    if _has_exotic_alphabet(text):
        return False
    cyrillic = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    latin = sum(1 for c in text if "A" <= c <= "Z" or "a" <= c <= "z")
    return cyrillic >= latin


def _normalize_analysis_payload(parsed: object) -> GeminiAnalysisPayload:
    if not isinstance(parsed, dict):
        raise TypeError("Gemini response payload must be a JSON object.")

    try:
        summary_value = parsed["summary_ru"] if "summary_ru" in parsed else parsed["summary"]
        coerced_summary = _coerce_scalar_to_string(summary_value, field_name="summary_ru")
        # Discard summary if it's primarily Latin (garbled transliteration)
        clean_summary = coerced_summary if _is_mostly_cyrillic(coerced_summary) else ""

        coerced_verdict = _coerce_scalar_to_string(parsed["verdict"], field_name="verdict")
        normalized_verdict = coerced_verdict if coerced_verdict in _VALID_VERDICTS else ""

        raw_format = _coerce_scalar_to_string(parsed["format"], field_name="format").lower()
        normalized_format = raw_format if raw_format in _VALID_FORMATS else ""

        raw_depth = _coerce_scalar_to_string(parsed["technical_depth"], field_name="technical_depth").lower()
        normalized_depth = raw_depth if raw_depth in _VALID_DEPTHS else ""

        raw_verdict_reason = _coerce_scalar_to_string(parsed["verdict_reason"], field_name="verdict_reason")
        # verdict_reason is supposed to be English — discard if the model wrote Russian instead
        cyrillic_vr = sum(1 for c in raw_verdict_reason if "Ѐ" <= c <= "ӿ")
        latin_vr = sum(1 for c in raw_verdict_reason if "A" <= c <= "Z" or "a" <= c <= "z")
        verdict_reason = raw_verdict_reason if latin_vr >= cyrillic_vr else ""

        return GeminiAnalysisPayload(
            summary_ru=clean_summary,
            topics=_coerce_topics(parsed["topics"]),
            format=normalized_format,
            technical_depth=normalized_depth,
            verdict=normalized_verdict,
            verdict_reason=verdict_reason,
        )
    except KeyError as exc:
        raise TypeError(f"Gemini response missing required field: {exc}") from exc


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
            f"Gemini field '{field_name}' must be JSON-serializable into the internal string contract."
        ) from exc
