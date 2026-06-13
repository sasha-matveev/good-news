from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from app.core.config import Settings
from app.core.observability import record_gemini_rate_limited

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker, Session
    from app.services.analysis import AnalysisRequest, AnalysisResult

logger = logging.getLogger(__name__)

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Free tier is request-starved, not token-starved: plenty of TPM headroom but a
# tight RPM cap. We trade the abundant resource (tokens) for the scarce one
# (requests) by packing several articles into one call.
CONTENT_SNIPPET_CHARS = 4000


@dataclass(frozen=True)
class GeminiAnalysisPayload:
    summary_ru: str
    topics: list[str]
    format: str
    technical_depth: str
    verdict: str
    verdict_reason: str


@dataclass(frozen=True)
class ArticleInput:
    post_id: int
    title: str
    content: str


_JSON_FIELDS_SPEC = (
    "JSON fields per article:\n"
    '  "summary_ru": a detailed summary in Russian (Кириллица), 4-6 sentences (roughly 60-120 words). '
    "Cover what the article is about, its key points, arguments or findings, and the concrete takeaway — "
    "enough that the reader understands the substance without opening the article. "
    "Do not just rephrase the title; add the specifics from the body. "
    "Use only Russian words — no Latin, no code, no transliteration. "
    'If you cannot write proper Russian, use "".\n'
    '  "verdict_reason": 1 sentence in ENGLISH explaining why a developer would or would not want to read this. '
    "MUST be in English. No Russian.\n"
    '  "verdict": "interesting" if worth reading for a developer, otherwise "not_interesting".\n'
    '  "topics": array of 1-3 short English tags like ["AI", "performance", "testing"].\n'
    '  "format": one of tutorial|opinion|news|case-study|announcement|other.\n'
    '  "technical_depth": one of beginner|intermediate|advanced.\n'
)


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
        self._min_interval = 60.0 / max(1, self.settings.gemini_max_rpm)
        self._next_allowed_at = 0.0

    # ---- single-article path (used by the standalone analysis service) ----

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
        prompt = (
            "You are a JSON-only API. Read the article and return ONE JSON object. No explanation, no markdown.\n"
            "\n"
            + _JSON_FIELDS_SPEC
            + "\n"
            f"Title: {title}\n"
            f"Content: {content[:CONTENT_SNIPPET_CHARS]}"
        )
        text = self._generate(prompt)
        return _normalize_analysis_payload(json.loads(text))

    # ---- batch path (used by source sync and the pending-analysis job) ----

    def analyze_and_persist_batch(self, requests: list["AnalysisRequest"]) -> list[int]:
        """Analyze many posts with few API calls; persist each result.

        Returns the post ids that could not be analyzed (missing from the model
        response or rejected), so callers can record failures and leave those
        posts pending for the next cycle.
        """
        from app.core.db import session_scope
        from app.services.analysis import AnalysisResult, persist_analysis_result

        items = [ArticleInput(post_id=r.post_id, title=r.title, content=r.content) for r in requests]
        payloads = self.analyze_articles(items)

        failed: list[int] = []
        if self._session_factory is None:
            return [item.post_id for item in items if item.post_id not in payloads]

        with session_scope(self._session_factory) as session:
            for request in requests:
                payload = payloads.get(request.post_id)
                if payload is None:
                    failed.append(request.post_id)
                    continue
                result = AnalysisResult(
                    summary_ru=payload.summary_ru,
                    topics=list(payload.topics),
                    format=payload.format,
                    technical_depth=payload.technical_depth,
                    verdict=payload.verdict,
                    verdict_reason=payload.verdict_reason,
                )
                persist_analysis_result(session=session, request=request, result=result)
            session.commit()
        return failed

    def analyze_articles(self, items: list[ArticleInput]) -> dict[int, GeminiAnalysisPayload]:
        results: dict[int, GeminiAnalysisPayload] = {}
        batch_size = max(1, self.settings.gemini_batch_size)
        for start in range(0, len(items), batch_size):
            chunk = items[start : start + batch_size]
            try:
                results.update(self._analyze_chunk(chunk))
            except Exception:
                logger.exception("Gemini batch chunk failed for post ids %s", [i.post_id for i in chunk])
        return results

    def _analyze_chunk(self, chunk: list[ArticleInput]) -> dict[int, GeminiAnalysisPayload]:
        articles_block = "\n\n".join(
            f"[id={item.post_id}]\nTitle: {item.title}\nContent: {item.content[:CONTENT_SNIPPET_CHARS]}"
            for item in chunk
        )
        prompt = (
            "You are a JSON-only API. Analyze EVERY article below and return ONE JSON object. "
            "No explanation, no markdown.\n"
            "\n"
            'Return: {"results": [ {"id": <the id given for the article>, ...fields...}, ... ]}\n'
            "Echo back the exact id for each article. Include every id exactly once.\n"
            "\n"
            + _JSON_FIELDS_SPEC
            + "\n"
            f"Articles:\n{articles_block}"
        )
        text = self._generate(prompt)
        parsed = json.loads(text)
        return _normalize_batch_payload(parsed, expected_ids={item.post_id for item in chunk})

    # ---- HTTP with throttle + retry ----

    def _generate(self, prompt: str) -> str:
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }
        url = f"{GEMINI_API_BASE_URL}/models/{self.settings.gemini_model}:generateContent"
        headers = {"x-goog-api-key": self.settings.gemini_api_key()}

        max_attempts = max(1, self.settings.gemini_max_retries)
        for attempt in range(1, max_attempts + 1):
            self._throttle()
            response = self.client.post(url, headers=headers, json=body)
            if response.status_code == 429 and attempt < max_attempts:
                delay = _retry_delay_seconds(response, attempt)
                logger.warning("Gemini 429 (attempt %d/%d); backing off %.1fs", attempt, max_attempts, delay)
                record_gemini_rate_limited(model=self.settings.gemini_model, attempt=attempt)
                time.sleep(delay)
                continue
            response.raise_for_status()
            raw_payload = response.json()
            try:
                return raw_payload["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as exc:
                raise TypeError(f"Gemini response missing candidate text: {exc}") from exc
        raise RuntimeError("Gemini request exhausted retries without a response.")

    def _throttle(self) -> None:
        now = time.monotonic()
        if now < self._next_allowed_at:
            time.sleep(self._next_allowed_at - now)
        self._next_allowed_at = time.monotonic() + self._min_interval


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    # Exponential backoff: 2s, 4s, 8s, ...
    return float(2**attempt)


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


def _normalize_batch_payload(
    parsed: object,
    expected_ids: set[int],
) -> dict[int, GeminiAnalysisPayload]:
    if not isinstance(parsed, dict):
        raise TypeError("Gemini batch response payload must be a JSON object.")
    raw_results = parsed.get("results")
    if not isinstance(raw_results, list):
        raise TypeError("Gemini batch response must contain a 'results' array.")

    by_id: dict[int, GeminiAnalysisPayload] = {}
    for entry in raw_results:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        try:
            entry_id = int(entry["id"])
        except (TypeError, ValueError):
            continue
        if entry_id not in expected_ids:
            continue
        try:
            by_id[entry_id] = _normalize_analysis_payload(entry)
        except (TypeError, KeyError):
            logger.warning("Gemini batch: could not normalize analysis for post id %s", entry_id)
    return by_id


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
