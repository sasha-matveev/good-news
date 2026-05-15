from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.jobs.digest_jobs import catch_up_daily_digest_if_needed, register_daily_digest_job
from app.services.source_sync import sync_active_sources

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover - fallback for local environments without APScheduler installed
    class BackgroundScheduler:  # type: ignore[override]
        def __init__(self, timezone: str = "UTC") -> None:
            self.jobs: list[dict[str, Any]] = []
            self.running = False

        def add_job(self, func: Callable[..., Any], trigger: str, id: str, replace_existing: bool, **kwargs: Any) -> None:
            self.jobs = [job for job in self.jobs if job["id"] != id]
            self.jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "id": id,
                    "replace_existing": replace_existing,
                    **kwargs,
                }
            )

        def start(self) -> None:
            self.running = True

        def shutdown(self, wait: bool = True) -> None:
            self.running = False


def create_scheduler(
    session_factory: sessionmaker[Session],
    responses: dict[str, str],
    settings: Settings,
    now_provider: Callable[[], datetime],
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: sync_active_sources(
            session_factory=session_factory,
            responses=responses,
            now=now_provider(),
            failure_threshold=settings.source_failure_threshold,
        ),
        trigger="interval",
        id="source-sync",
        minutes=settings.source_sync_interval_minutes,
        replace_existing=True,
    )
    register_daily_digest_job(
        scheduler=scheduler,
        session_factory=session_factory,
        now_provider=now_provider,
    )
    catch_up_daily_digest_if_needed(
        session_factory=session_factory,
        now=now_provider(),
        run_digest=lambda scheduled_for: None,
    )
    return scheduler
