from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.db import session_scope
from app.core.observability import record_delivery_run
from app.models.digest import Digest
from app.services.digest_service import generate_daily_digest, generate_weekly_digest
from app.services.email_service import EmailMessage, EmailSendError, EmailTransport, SmtpTransport, send_email
from app.services.observability_report_service import generate_daily_observability_report
from app.services.settings_service import (
    get_last_observability_report_sent_at,
    get_last_daily_digest_sent_at,
    get_last_weekly_digest_sent_at,
    get_smtp_password,
    load_settings,
    set_last_observability_report_sent_at,
    set_last_daily_digest_sent_at,
    set_last_weekly_digest_sent_at,
)


@dataclass(frozen=True)
class DeliveryRunResult:
    digest_id: int
    status: str
    delivered: bool
    item_count: int


def _parse_daily_time(raw_value: str) -> tuple[int, int]:
    hour_text, minute_text = raw_value.split(":")
    return int(hour_text), int(minute_text)


def _parse_weekly_day(raw_value: str) -> int:
    return {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }[raw_value]


def _last_due_time(*, now: datetime, daily_digest_time: str) -> datetime:
    hour, minute = _parse_daily_time(daily_digest_time)
    due_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= due_today:
        return due_today - timedelta(days=1)
    return due_today - timedelta(days=2)


def _latest_due_time_including_today(*, now: datetime, scheduled_time: str) -> datetime:
    hour, minute = _parse_daily_time(scheduled_time)
    due_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= due_today:
        return due_today
    return due_today - timedelta(days=1)


def _last_weekly_due_time(*, now: datetime, weekly_digest_day_of_week: str, weekly_digest_time: str) -> datetime:
    hour, minute = _parse_daily_time(weekly_digest_time)
    target_weekday = _parse_weekly_day(weekly_digest_day_of_week)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_since_target = (now.weekday() - target_weekday) % 7
    candidate = candidate - timedelta(days=days_since_target)
    if now < candidate:
        candidate -= timedelta(days=7)
    return candidate


def _deliver_generated_digest(
    *,
    session_factory: sessionmaker[Session],
    now: datetime,
    runtime_settings: Settings,
    email_transport: EmailTransport | None,
    digest_type: str,
    generate_digest: Callable[[Session], object],
    set_last_sent_at: Callable[[Session, str], None],
) -> DeliveryRunResult:
    with session_scope(session_factory) as session:
        app_settings = load_settings(session)
        try:
            digest = generate_digest(session)
        except Exception:
            record_delivery_run(digest_type=digest_type, status="failed")
            raise
        item_count = _generated_item_count(digest)
        stored_digest = session.get(Digest, digest.digest_id)
        if stored_digest is None:
            raise LookupError(f"Digest {digest.digest_id} was not persisted")
        if not app_settings.recipient_email or not app_settings.sender_identity:
            stored_digest.status = "skipped"
            set_last_sent_at(session, now.astimezone(UTC).isoformat())
            record_delivery_run(digest_type=digest_type, status="skipped")
            return DeliveryRunResult(
                digest_id=digest.digest_id,
                status="skipped",
                delivered=False,
                item_count=item_count,
            )
        transport = email_transport or SmtpTransport(
            host=app_settings.smtp_host or "",
            port=app_settings.smtp_port,
            username=app_settings.smtp_username,
            password=get_smtp_password(session, runtime_settings.app_master_key()),
            security_mode=app_settings.smtp_security_mode,
        )
        try:
            send_email(
                EmailMessage(
                    sender=app_settings.sender_identity,
                    recipient=app_settings.recipient_email,
                    subject=digest.subject,
                    html_body=digest.html_body,
                ),
                transport=transport,
            )
        except EmailSendError:
            stored_digest.status = "failed"
            record_delivery_run(digest_type=digest_type, status="failed")
            raise
        stored_digest.status = "sent"
        stored_digest.recipient_email = app_settings.recipient_email
        stored_digest.sent_at = now
        set_last_sent_at(session, now.astimezone(UTC).isoformat())
        record_delivery_run(digest_type=digest_type, status="sent")
        return DeliveryRunResult(
            digest_id=digest.digest_id,
            status="sent",
            delivered=True,
            item_count=item_count,
        )


def _generated_item_count(result: object) -> int:
    explicit_item_count = getattr(result, "item_count", None)
    if isinstance(explicit_item_count, int):
        return explicit_item_count
    posts = getattr(result, "posts", None)
    if isinstance(posts, list):
        return len(posts)
    return 0


def run_daily_digest(
    *,
    session_factory: sessionmaker[Session],
    now: datetime,
    runtime_settings: Settings | None = None,
    email_transport: EmailTransport | None = None,
) -> DeliveryRunResult:
    resolved_runtime_settings = runtime_settings or Settings.from_env()
    return _deliver_generated_digest(
        session_factory=session_factory,
        now=now,
        runtime_settings=resolved_runtime_settings,
        email_transport=email_transport,
        digest_type="daily",
        generate_digest=lambda session: generate_daily_digest(
            session=session,
            now=now,
            frontend_base_url=resolved_runtime_settings.frontend_public_origin_url(),
            content_api_base_url=resolved_runtime_settings.content_api_public_origin_url(),
        ),
        set_last_sent_at=set_last_daily_digest_sent_at,
    )


def run_weekly_digest(
    *,
    session_factory: sessionmaker[Session],
    now: datetime,
    runtime_settings: Settings | None = None,
    email_transport: EmailTransport | None = None,
) -> DeliveryRunResult:
    resolved_runtime_settings = runtime_settings or Settings.from_env()
    return _deliver_generated_digest(
        session_factory=session_factory,
        now=now,
        runtime_settings=resolved_runtime_settings,
        email_transport=email_transport,
        digest_type="weekly",
        generate_digest=lambda session: generate_weekly_digest(
            session=session,
            now=now,
            frontend_base_url=resolved_runtime_settings.frontend_public_origin_url(),
            content_api_base_url=resolved_runtime_settings.content_api_public_origin_url(),
        ),
        set_last_sent_at=set_last_weekly_digest_sent_at,
    )


def run_daily_observability_report(
    *,
    session_factory: sessionmaker[Session],
    now: datetime,
    runtime_settings: Settings | None = None,
    email_transport: EmailTransport | None = None,
) -> DeliveryRunResult:
    resolved_runtime_settings = runtime_settings or Settings.from_env()
    return _deliver_generated_digest(
        session_factory=session_factory,
        now=now,
        runtime_settings=resolved_runtime_settings,
        email_transport=email_transport,
        digest_type="observability_daily",
        generate_digest=lambda session: generate_daily_observability_report(
            session=session,
            now=now,
            grafana_base_url=resolved_runtime_settings.observability_grafana_base_url(),
        ),
        set_last_sent_at=set_last_observability_report_sent_at,
    )


def catch_up_daily_digest_if_needed(
    *,
    session_factory: sessionmaker[Session],
    now: datetime,
    run_digest: Callable[[datetime], object],
) -> datetime | None:
    with session_scope(session_factory) as session:
        settings = load_settings(session)
        if not settings.daily_digest_catch_up_enabled or not settings.daily_digest_enabled:
            return None
        last_due = _last_due_time(now=now, daily_digest_time=settings.daily_digest_time)
        last_sent = get_last_daily_digest_sent_at(session)
        if last_sent is not None and datetime.fromisoformat(last_sent) >= last_due:
            return None
        run_digest(last_due)
        set_last_daily_digest_sent_at(session, last_due.astimezone(UTC).isoformat())
        return last_due


def catch_up_weekly_digest_if_needed(
    *,
    session_factory: sessionmaker[Session],
    now: datetime,
    run_digest: Callable[[datetime], object],
) -> datetime | None:
    with session_scope(session_factory) as session:
        settings = load_settings(session)
        if not settings.weekly_digest_catch_up_enabled or not settings.weekly_digest_enabled:
            return None
        last_due = _last_weekly_due_time(
            now=now,
            weekly_digest_day_of_week=settings.weekly_digest_day_of_week,
            weekly_digest_time=settings.weekly_digest_time,
        )
        last_sent = get_last_weekly_digest_sent_at(session)
        if last_sent is not None and datetime.fromisoformat(last_sent) >= last_due:
            return None
        run_digest(last_due)
        set_last_weekly_digest_sent_at(session, last_due.astimezone(UTC).isoformat())
        return last_due


def catch_up_daily_observability_report_if_needed(
    *,
    session_factory: sessionmaker[Session],
    now: datetime,
    runtime_settings: Settings | None = None,
    run_report: Callable[[datetime], object],
) -> datetime | None:
    resolved_runtime_settings = runtime_settings or Settings.from_env()
    with session_scope(session_factory) as session:
        last_due = _latest_due_time_including_today(
            now=now,
            scheduled_time=resolved_runtime_settings.observability_daily_report_time,
        )
        last_sent = get_last_observability_report_sent_at(session)
        if last_sent is not None and datetime.fromisoformat(last_sent) >= last_due:
            return None
        run_report(last_due)
        set_last_observability_report_sent_at(session, last_due.astimezone(UTC).isoformat())
        return last_due


def register_daily_digest_job(
    *,
    scheduler: object,
    session_factory: sessionmaker[Session],
    now_provider: Callable[[], datetime],
    runtime_settings: Settings | None = None,
) -> None:
    resolved_runtime_settings = runtime_settings or Settings.from_env()
    with session_scope(session_factory) as session:
        settings = load_settings(session)
    hour, minute = _parse_daily_time(settings.daily_digest_time)
    scheduler.add_job(
        lambda: run_daily_digest(
            session_factory=session_factory,
            now=now_provider(),
            runtime_settings=resolved_runtime_settings,
        ),
        trigger="cron",
        id="daily-digest",
        hour=hour,
        minute=minute,
        replace_existing=True,
    )


def register_weekly_digest_job(
    *,
    scheduler: object,
    session_factory: sessionmaker[Session],
    now_provider: Callable[[], datetime],
    runtime_settings: Settings | None = None,
) -> None:
    resolved_runtime_settings = runtime_settings or Settings.from_env()
    with session_scope(session_factory) as session:
        settings = load_settings(session)
    if not settings.weekly_digest_enabled:
        return
    hour, minute = _parse_daily_time(settings.weekly_digest_time)
    scheduler.add_job(
        lambda: run_weekly_digest(
            session_factory=session_factory,
            now=now_provider(),
            runtime_settings=resolved_runtime_settings,
        ),
        trigger="cron",
        id="weekly-digest",
        day_of_week=settings.weekly_digest_day_of_week,
        hour=hour,
        minute=minute,
        replace_existing=True,
    )


def register_daily_observability_report_job(
    *,
    scheduler: object,
    session_factory: sessionmaker[Session],
    now_provider: Callable[[], datetime],
    runtime_settings: Settings | None = None,
) -> None:
    resolved_runtime_settings = runtime_settings or Settings.from_env()
    hour, minute = _parse_daily_time(resolved_runtime_settings.observability_daily_report_time)
    scheduler.add_job(
        lambda: run_daily_observability_report(
            session_factory=session_factory,
            now=now_provider(),
            runtime_settings=resolved_runtime_settings,
        ),
        trigger="cron",
        id="observability-daily-report",
        hour=hour,
        minute=minute,
        replace_existing=True,
    )


def reload_daily_digest_job(
    *,
    scheduler: object,
    session_factory: sessionmaker[Session],
    now_provider: Callable[[], datetime],
    runtime_settings: Settings | None = None,
) -> None:
    register_daily_digest_job(
        scheduler=scheduler,
        session_factory=session_factory,
        now_provider=now_provider,
        runtime_settings=runtime_settings,
    )
