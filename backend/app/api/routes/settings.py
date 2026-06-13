from __future__ import annotations

from collections.abc import Generator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.db import session_scope
from app.jobs.digest_jobs import register_daily_digest_job, register_weekly_digest_job
from app.schemas.setting import SettingsResponse, SettingsUpdateRequest
from app.services.delivery_boundary import DELIVERY_OWNED_SETTING_KEYS, send_test_email_command
from app.services.delivery_service_client import DeliveryServiceClient
from app.services.settings_service import AppSettingsUpdate, load_settings, save_settings

router = APIRouter(tags=["settings"])


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


def _is_monolith(request: Request) -> bool:
    """Return True when running in the merged monolith (no delivery service HTTP hop)."""
    return getattr(request.app.state, "analysis_client_factory", None) is not None


@router.get("/settings", response_model=SettingsResponse)
def get_settings(request: Request, session: Session = Depends(get_session)) -> SettingsResponse:
    settings = load_settings(session)
    return SettingsResponse(
        **settings.__dict__,
        observability_dashboard_url=request.app.state.settings.observability_dashboard_url(),
    )


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> SettingsResponse:
    master_key = getattr(request.app.state, "app_master_key", None) or Settings.from_env().app_master_key()
    save_settings(
        session,
        AppSettingsUpdate(
            daily_digest_time=payload.daily_digest_time,
            weekly_digest_day_of_week=payload.weekly_digest_day_of_week,
            weekly_digest_time=payload.weekly_digest_time,
            recipient_email=payload.recipient_email,
            sender_identity=payload.sender_identity,
            smtp_host=payload.smtp_host,
            smtp_port=payload.smtp_port,
            smtp_username=payload.smtp_username,
            smtp_security_mode=payload.smtp_security_mode,
            daily_digest_enabled=payload.daily_digest_enabled,
            daily_digest_catch_up_enabled=payload.daily_digest_catch_up_enabled,
            weekly_digest_enabled=payload.weekly_digest_enabled,
            weekly_digest_catch_up_enabled=payload.weekly_digest_catch_up_enabled,
            smtp_password=payload.smtp_password,
            analysis_summary_prompt=payload.analysis_summary_prompt,
            analysis_verdict_reason_prompt=payload.analysis_verdict_reason_prompt,
        ),
        master_key,
    )
    # Commit before returning so the next proxied GET observes the persisted state deterministically.
    session.commit()
    settings = load_settings(session)
    request.app.state.delivery_owned_setting_keys = DELIVERY_OWNED_SETTING_KEYS

    # Re-register scheduler jobs so changed digest times/days take effect immediately
    # without requiring an app restart.
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        now_provider = getattr(request.app.state, "now_provider", None)
        runtime_settings = getattr(request.app.state, "settings", None)
        session_factory = getattr(request.app.state, "session_factory", None)
        if now_provider is not None and session_factory is not None:
            register_daily_digest_job(
                scheduler=scheduler,
                session_factory=session_factory,
                now_provider=now_provider,
                runtime_settings=runtime_settings,
            )
            register_weekly_digest_job(
                scheduler=scheduler,
                session_factory=session_factory,
                now_provider=now_provider,
                runtime_settings=runtime_settings,
            )

    return SettingsResponse(
        **settings.__dict__,
        observability_dashboard_url=request.app.state.settings.observability_dashboard_url(),
    )


@router.post("/settings/test-email")
def test_email(
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    # Monolith path: call delivery boundary directly.
    if _is_monolith(request):
        factory = getattr(request.app.state, "email_transport_factory", None)
        transport = factory(session) if factory is not None else None
        send_test_email_command(
            session=session,
            runtime_settings=request.app.state.settings,
            email_transport=transport,
            app_master_key=getattr(request.app.state, "app_master_key", None),
        )
        return {"status": "sent"}

    # Legacy microservice path: delegate via HTTP client.
    factory = getattr(request.app.state, "delivery_service_client_factory", None)
    if factory is None:
        client: DeliveryServiceClient = DeliveryServiceClient(settings=request.app.state.settings)
    else:
        client = factory()
    try:
        return client.send_test_email()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Delivery service is unavailable.") from exc
