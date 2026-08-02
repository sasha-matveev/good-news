from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import MissingPublicOriginError
from app.core.request_auth import _bearer_token, google_oidc_token_verifier
from app.jobs.digest_jobs import (
    catch_up_daily_digest_if_needed,
    catch_up_weekly_digest_if_needed,
    run_daily_digest,
    run_weekly_digest,
)
from app.services.email_service import EmailSendError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["internal-jobs"])


class SourceSyncJobResponse(BaseModel):
    processed_source_ids: list[int]
    analyzed_pending: bool


class DigestJobResponse(BaseModel):
    daily_ran_for: str | None
    weekly_ran_for: str | None
    errors: list[str]


def _require_scheduler_oidc(request: Request) -> None:
    """Reject requests that do not carry a valid OIDC token from the scheduler SA."""
    settings = request.app.state.settings
    if not settings.scheduler_invoker:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler invoker is not configured.",
        )

    token = _bearer_token(request)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    verifier = getattr(request.app.state, "scheduler_oidc_verifier", None)
    if verifier is None:
        verifier = google_oidc_token_verifier(audience=settings.oidc_audience)
        request.app.state.scheduler_oidc_verifier = verifier

    try:
        claims = verifier(token)
    except Exception as exc:
        logger.warning("Rejected internal job call with invalid OIDC token: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc

    email = str(claims.get("email", "")).lower()
    if not claims.get("email_verified") or email != settings.scheduler_invoker.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")


@router.post("/internal/jobs/source-sync", response_model=SourceSyncJobResponse)
def run_source_sync_job(request: Request) -> SourceSyncJobResponse:
    _require_scheduler_oidc(request)

    from app.services.source_sync import sync_active_sources

    state = request.app.state
    processed_source_ids = sync_active_sources(
        session_factory=state.session_factory,
        responses=getattr(state, "responses", {}),
        document_loader=getattr(state, "document_loader", None),
        now=state.now_provider(),
        failure_threshold=state.settings.source_failure_threshold,
        analysis_service_client=state.analysis_client_factory(),
    )

    analyzed = False
    try:
        from app.jobs.analysis_jobs import analyze_pending_posts

        analyze_pending_posts(
            session_factory=state.session_factory,
            analysis_client=state.analysis_client_factory(),
        )
        analyzed = True
    except Exception:
        logger.exception("source-sync job: analyze_pending_posts failed")

    return SourceSyncJobResponse(
        processed_source_ids=processed_source_ids,
        analyzed_pending=analyzed,
    )


@router.post("/internal/jobs/digests", response_model=DigestJobResponse)
def run_digest_jobs(request: Request) -> DigestJobResponse:
    _require_scheduler_oidc(request)

    state = request.app.state
    settings = state.settings
    now = state.now_provider()
    errors: list[str] = []
    daily_ran_for: str | None = None
    weekly_ran_for: str | None = None

    try:
        ran = catch_up_daily_digest_if_needed(
            session_factory=state.session_factory,
            now=now,
            run_digest=lambda scheduled_for: run_daily_digest(
                session_factory=state.session_factory,
                now=scheduled_for,
                runtime_settings=settings,
            ),
        )
        daily_ran_for = ran.isoformat() if ran else None
    except (EmailSendError, MissingPublicOriginError) as exc:
        logger.warning("digests job: daily digest failed: %s", exc)
        errors.append(f"daily: {exc}")

    try:
        ran = catch_up_weekly_digest_if_needed(
            session_factory=state.session_factory,
            now=now,
            run_digest=lambda scheduled_for: run_weekly_digest(
                session_factory=state.session_factory,
                now=scheduled_for,
                runtime_settings=settings,
            ),
        )
        weekly_ran_for = ran.isoformat() if ran else None
    except (EmailSendError, MissingPublicOriginError) as exc:
        logger.warning("digests job: weekly digest failed: %s", exc)
        errors.append(f"weekly: {exc}")

    return DigestJobResponse(
        daily_ran_for=daily_ran_for,
        weekly_ran_for=weekly_ran_for,
        errors=errors,
    )
