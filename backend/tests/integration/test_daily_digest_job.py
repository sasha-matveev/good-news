from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import Settings
from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.jobs.digest_jobs import (
    catch_up_daily_observability_report_if_needed,
    catch_up_daily_digest_if_needed,
    register_daily_observability_report_job,
    catch_up_weekly_digest_if_needed,
    run_daily_observability_report,
    register_weekly_digest_job,
)
from app.models.base import Base
from app.models.digest import Digest
from app.models.setting import TechnicalEvent
from app.models.setting import Setting
from app.models.source import Source


def test_startup_catch_up_runs_only_latest_missed_daily_digest() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    invocations: list[datetime] = []

    with session_scope(session_factory) as session:
        session.add(Setting(key="daily_digest_time", value="12:00"))
        session.add(Setting(key="daily_digest_catch_up_enabled", value="true"))
        session.add(Setting(key="last_daily_digest_sent_at", value="2026-04-23T12:00:00+00:00"))

    catch_up_daily_digest_if_needed(
        session_factory=session_factory,
        now=datetime(2026, 4, 26, 12, 5, tzinfo=UTC),
        run_digest=lambda scheduled_for: invocations.append(scheduled_for),
    )

    assert invocations == [datetime(2026, 4, 25, 12, 0, tzinfo=UTC)]


def test_startup_catch_up_runs_latest_missed_weekly_digest() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    invocations: list[datetime] = []

    with session_scope(session_factory) as session:
        session.add(Setting(key="weekly_digest_day_of_week", value="mon"))
        session.add(Setting(key="weekly_digest_time", value="09:30"))
        session.add(Setting(key="weekly_digest_enabled", value="true"))
        session.add(Setting(key="weekly_digest_catch_up_enabled", value="true"))
        session.add(Setting(key="last_weekly_digest_sent_at", value="2026-04-20T09:30:00+00:00"))

    catch_up_weekly_digest_if_needed(
        session_factory=session_factory,
        now=datetime(2026, 5, 3, 12, 5, tzinfo=UTC),
        run_digest=lambda scheduled_for: invocations.append(scheduled_for),
    )

    assert invocations == [datetime(2026, 4, 27, 9, 30, tzinfo=UTC)]


def test_register_weekly_digest_job_uses_configured_weekday_and_time() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    class RecordingScheduler:
        def __init__(self) -> None:
            self.jobs: list[dict[str, object]] = []

        def add_job(self, func, trigger: str, id: str, replace_existing: bool, **kwargs) -> None:
            self.jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "id": id,
                    "replace_existing": replace_existing,
                    **kwargs,
                }
            )

    with session_scope(session_factory) as session:
        session.add(Setting(key="weekly_digest_enabled", value="true"))
        session.add(Setting(key="weekly_digest_day_of_week", value="fri"))
        session.add(Setting(key="weekly_digest_time", value="16:45"))

    scheduler = RecordingScheduler()

    register_weekly_digest_job(
        scheduler=scheduler,
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 5, 1, 16, 45, tzinfo=UTC),
    )

    assert scheduler.jobs == [
        {
            "func": scheduler.jobs[0]["func"],
            "trigger": "cron",
            "id": "weekly-digest",
            "replace_existing": True,
            "day_of_week": "fri",
            "hour": 16,
            "minute": 45,
        }
    ]


def test_register_weekly_digest_job_skips_registration_when_weekly_disabled() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    class RecordingScheduler:
        def __init__(self) -> None:
            self.jobs: list[dict[str, object]] = []

        def add_job(self, func, trigger: str, id: str, replace_existing: bool, **kwargs) -> None:
            self.jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "id": id,
                    "replace_existing": replace_existing,
                    **kwargs,
                }
            )

    with session_scope(session_factory) as session:
        session.add(Setting(key="weekly_digest_enabled", value="false"))
        session.add(Setting(key="weekly_digest_day_of_week", value="fri"))
        session.add(Setting(key="weekly_digest_time", value="16:45"))

    scheduler = RecordingScheduler()

    register_weekly_digest_job(
        scheduler=scheduler,
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 5, 1, 16, 45, tzinfo=UTC),
    )

    assert scheduler.jobs == []


def test_register_daily_observability_report_job_uses_runtime_schedule() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    class RecordingScheduler:
        def __init__(self) -> None:
            self.jobs: list[dict[str, object]] = []

        def add_job(self, func, trigger: str, id: str, replace_existing: bool, **kwargs) -> None:
            self.jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "id": id,
                    "replace_existing": replace_existing,
                    **kwargs,
                }
            )

    scheduler = RecordingScheduler()

    register_daily_observability_report_job(
        scheduler=scheduler,
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 4, 26, 18, 0, tzinfo=UTC),
        runtime_settings=Settings(observability_daily_report_time="18:15"),
    )

    assert scheduler.jobs == [
        {
            "func": scheduler.jobs[0]["func"],
            "trigger": "cron",
            "id": "observability-daily-report",
            "replace_existing": True,
            "hour": 18,
            "minute": 15,
        }
    ]


def test_run_daily_observability_report_sends_email_and_persists_sent_digest() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 4, 26, 18, 0, tzinfo=UTC)

    class RecordingTransport:
        def __init__(self) -> None:
            self.sent_messages: list[object] = []

        def send(self, message) -> None:
            self.sent_messages.append(message)

    with session_scope(session_factory) as session:
        session.add_all(
            [
                Setting(key="recipient_email", value="ops@example.com"),
                Setting(key="sender_identity", value="Good News Ops <ops@example.com>"),
                Source(
                    id=1,
                    display_name="Alpha",
                    original_url="https://alpha.example",
                    status="failing",
                    consecutive_failures=2,
                    last_failure_at=now,
                    needs_readaptation=True,
                ),
                TechnicalEvent(
                    severity="warning",
                    subsystem="source-sync",
                    event_code="source.repeated_failure",
                    summary="Source sync hit the repeated-failure threshold.",
                    details="Alpha feed returned HTTP 500",
                    source_id=1,
                    created_at=now,
                ),
            ]
        )

    transport = RecordingTransport()
    result = run_daily_observability_report(
        session_factory=session_factory,
        now=now,
        runtime_settings=Settings(observability_grafana_origin="https://grafana.good-news.example"),
        email_transport=transport,
    )

    assert result.status == "sent"
    assert result.delivered is True
    assert result.item_count == 1
    assert len(transport.sent_messages) == 1
    assert "https://grafana.good-news.example/render/d-solo/good-news-overview" in transport.sent_messages[0].html_body

    with session_scope(session_factory) as session:
        digest = session.scalar(select(Digest).where(Digest.id == result.digest_id))
        sent_marker = session.scalar(select(Setting).where(Setting.key == "last_observability_report_sent_at"))

    assert digest is not None
    assert digest.digest_type == "observability_daily"
    assert digest.status == "sent"
    assert digest.recipient_email == "ops@example.com"
    assert digest.sent_at == now.replace(tzinfo=None)
    assert sent_marker is not None
    assert sent_marker.value == "2026-04-26T18:00:00+00:00"


def test_startup_catch_up_runs_latest_missed_observability_report() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    invocations: list[datetime] = []

    with session_scope(session_factory) as session:
        session.add(Setting(key="last_observability_report_sent_at", value="2026-04-23T18:00:00+00:00"))

    catch_up_daily_observability_report_if_needed(
        session_factory=session_factory,
        now=datetime(2026, 4, 26, 18, 5, tzinfo=UTC),
        runtime_settings=Settings(observability_daily_report_time="18:00"),
        run_report=lambda scheduled_for: invocations.append(scheduled_for),
    )

    assert invocations == [datetime(2026, 4, 26, 18, 0, tzinfo=UTC)]


def test_startup_catch_up_runs_same_day_observability_report_when_startup_is_just_after_due_time() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    invocations: list[datetime] = []

    with session_scope(session_factory) as session:
        session.add(Setting(key="last_observability_report_sent_at", value="2026-04-25T18:00:00+00:00"))

    catch_up_daily_observability_report_if_needed(
        session_factory=session_factory,
        now=datetime(2026, 4, 26, 18, 5, tzinfo=UTC),
        runtime_settings=Settings(observability_daily_report_time="18:00"),
        run_report=lambda scheduled_for: invocations.append(scheduled_for),
    )

    assert invocations == [datetime(2026, 4, 26, 18, 0, tzinfo=UTC)]
