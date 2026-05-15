from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory, session_scope
from app.core.observability import instrument_app
from app.core.schema_guard import assert_database_schema_is_current
from app.jobs.digest_jobs import (
    catch_up_daily_observability_report_if_needed,
    catch_up_daily_digest_if_needed,
    catch_up_weekly_digest_if_needed,
    register_daily_observability_report_job,
    register_daily_digest_job,
    register_weekly_digest_job,
    run_daily_observability_report,
    run_daily_digest,
    run_weekly_digest,
)
from app.services.delivery_boundary import send_test_email_command
from app.services.email_service import EmailSendError

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover
    class BackgroundScheduler:  # type: ignore[override]
        def __init__(self, timezone: str = "UTC") -> None:
            self.jobs: list[dict[str, Any]] = []
            self.running = False

        def add_job(self, func: Callable[..., Any], trigger: str, id: str, replace_existing: bool, **kwargs: Any) -> None:
            self.jobs = [job for job in self.jobs if job["id"] != id]
            self.jobs.append({"func": func, "trigger": trigger, "id": id, "replace_existing": replace_existing, **kwargs})

        def start(self) -> None:
            self.running = True

        def shutdown(self, wait: bool = True) -> None:
            self.running = False


class DeliveryStatusResponse(BaseModel):
    status: str


class DailyDigestRunResponse(BaseModel):
    digest_id: int
    status: str
    delivered: bool
    item_count: int


class CatchUpResponse(BaseModel):
    scheduled_for: str | None
def create_app(
    session_factory: sessionmaker[Session] | None = None,
    settings: Settings | None = None,
    enable_scheduler: bool = True,
    now_provider: Callable[[], datetime] | None = None,
    email_transport_factory: Callable[[Session], object | None] | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_now_provider = now_provider or (lambda: datetime.now(UTC))
    app = FastAPI(title="Good News Delivery Service")
    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.enable_scheduler = enable_scheduler
    app.state.now_provider = resolved_now_provider
    app.state.scheduler = None
    app.state.email_transport_factory = email_transport_factory
    instrument_app(app=app, service_name="delivery-service")

    @app.on_event("startup")
    def ensure_runtime() -> None:
        if app.state.session_factory is None:
            engine = create_engine_from_settings(settings=resolved_settings)
            app.state.session_factory = create_session_factory(engine)
        assert_database_schema_is_current(app.state.session_factory)
        if app.state.enable_scheduler:
            scheduler = BackgroundScheduler(timezone="UTC")
            register_daily_digest_job(
                scheduler=scheduler,
                session_factory=app.state.session_factory,
                now_provider=app.state.now_provider,
                runtime_settings=resolved_settings,
            )
            register_weekly_digest_job(
                scheduler=scheduler,
                session_factory=app.state.session_factory,
                now_provider=app.state.now_provider,
                runtime_settings=resolved_settings,
            )
            register_daily_observability_report_job(
                scheduler=scheduler,
                session_factory=app.state.session_factory,
                now_provider=app.state.now_provider,
                runtime_settings=resolved_settings,
            )
            try:
                catch_up_daily_digest_if_needed(
                    session_factory=app.state.session_factory,
                    now=app.state.now_provider(),
                    run_digest=lambda scheduled_for: run_daily_digest(
                        session_factory=app.state.session_factory,
                        now=scheduled_for,
                        runtime_settings=resolved_settings,
                    ),
                )
            except EmailSendError as exc:
                logger.warning("Startup daily digest catch-up failed (will retry on next schedule): %s", exc)
            try:
                catch_up_daily_observability_report_if_needed(
                    session_factory=app.state.session_factory,
                    now=app.state.now_provider(),
                    runtime_settings=resolved_settings,
                    run_report=lambda scheduled_for: run_daily_observability_report(
                        session_factory=app.state.session_factory,
                        now=scheduled_for,
                        runtime_settings=resolved_settings,
                    ),
                )
            except EmailSendError as exc:
                logger.warning("Startup observability report catch-up failed (will retry on next schedule): %s", exc)
            try:
                catch_up_weekly_digest_if_needed(
                    session_factory=app.state.session_factory,
                    now=app.state.now_provider(),
                    run_digest=lambda scheduled_for: run_weekly_digest(
                        session_factory=app.state.session_factory,
                        now=scheduled_for,
                        runtime_settings=resolved_settings,
                    ),
                )
            except EmailSendError as exc:
                logger.warning("Startup weekly digest catch-up failed (will retry on next schedule): %s", exc)
            scheduler.start()
            app.state.scheduler = scheduler

    @app.on_event("shutdown")
    def shutdown_scheduler() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            app.state.scheduler = None

    def get_session_factory(request: Request) -> sessionmaker[Session]:
        return request.app.state.session_factory

    def get_session(
        session_factory: sessionmaker[Session] = Depends(get_session_factory),
    ) -> Generator[Session, None, None]:
        with session_scope(session_factory) as session:
            yield session

    @app.get("/health")
    def health(session: Session = Depends(get_session)) -> dict[str, str]:
        session.execute(select(1))
        return {"status": "ok"}

    @app.post("/internal/delivery/test-email", response_model=DeliveryStatusResponse)
    def test_email(request: Request, session: Session = Depends(get_session)) -> DeliveryStatusResponse:
        factory = getattr(request.app.state, "email_transport_factory", None)
        transport = factory(session) if factory is not None else None
        send_test_email_command(
            session=session,
            runtime_settings=request.app.state.settings,
            email_transport=transport,
            app_master_key=getattr(request.app.state, "app_master_key", None),
        )
        return DeliveryStatusResponse(status="sent")

    @app.post("/internal/delivery/digests/run-once", response_model=DailyDigestRunResponse)
    def run_digest_once(request: Request) -> DailyDigestRunResponse:
        factory = getattr(request.app.state, "email_transport_factory", None)
        with session_scope(request.app.state.session_factory) as session:
            transport = factory(session) if factory is not None else None
        result = run_daily_digest(
            session_factory=request.app.state.session_factory,
            now=request.app.state.now_provider(),
            runtime_settings=request.app.state.settings,
            email_transport=transport,
        )
        return DailyDigestRunResponse(**result.__dict__)

    @app.post("/internal/delivery/digests/catch-up/run-once", response_model=CatchUpResponse)
    def catch_up_once(request: Request) -> CatchUpResponse:
        factory = getattr(request.app.state, "email_transport_factory", None)

        def run_candidate(candidate: datetime) -> object:
            with session_scope(request.app.state.session_factory) as session:
                transport = factory(session) if factory is not None else None
            return run_daily_digest(
                session_factory=request.app.state.session_factory,
                now=candidate,
                runtime_settings=request.app.state.settings,
                email_transport=transport,
            )

        scheduled_for = catch_up_daily_digest_if_needed(
            session_factory=request.app.state.session_factory,
            now=request.app.state.now_provider(),
            run_digest=run_candidate,
        )
        return CatchUpResponse(
            scheduled_for=scheduled_for.astimezone(UTC).isoformat().replace("+00:00", "Z") if scheduled_for is not None else None
        )

    return app


app = create_app()
