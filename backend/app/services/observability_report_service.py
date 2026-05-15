from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
import json
from urllib.parse import urlencode

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.digest import Digest
from app.models.setting import TechnicalEvent
from app.models.source import Source

_DASHBOARD_UID = "good-news-overview"
_DASHBOARD_SLUG = "good-news-observability-overview"
_DASHBOARD_PANEL_ID = 1
_REPORT_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class ObservabilityReportResult:
    digest_id: int
    subject: str
    html_body: str
    item_count: int


@dataclass(frozen=True)
class _TechnicalEventSummary:
    severity: str
    subsystem: str
    event_code: str
    summary: str
    details: str | None
    source_name: str | None
    created_at: datetime


@dataclass(frozen=True)
class _FailingSourceSummary:
    display_name: str | None
    original_url: str
    status: str
    consecutive_failures: int
    needs_readaptation: bool
    last_failure_at: datetime | None


def generate_daily_observability_report(
    *,
    session: Session,
    now: datetime,
    grafana_base_url: str,
) -> ObservabilityReportResult:
    technical_events = _load_recent_technical_events(session=session, now=now)
    failing_sources = _load_failing_sources(session=session)
    dashboard_url, render_url = _build_grafana_urls(grafana_base_url=grafana_base_url)
    subject = f"Good News observability report for {now.astimezone(UTC).date().isoformat()}"
    html_body = _render_observability_report_email(
        subject=subject,
        now=now,
        technical_events=technical_events,
        failing_sources=failing_sources,
        dashboard_url=dashboard_url,
        render_url=render_url,
    )
    digest = Digest(
        digest_type="observability_daily",
        scheduled_for=now,
        status="generated",
        recipient_email=None,
        subject=subject,
        html_body=html_body,
        metadata_json=json.dumps(
            {
                "dashboard_url": dashboard_url,
                "render_url": render_url,
                "event_count": len(technical_events),
                "failing_source_count": len(failing_sources),
            }
        ),
    )
    session.add(digest)
    session.flush()
    return ObservabilityReportResult(
        digest_id=digest.id,
        subject=subject,
        html_body=html_body,
        item_count=len(technical_events),
    )


def _load_recent_technical_events(*, session: Session, now: datetime) -> list[_TechnicalEventSummary]:
    since = now - _REPORT_WINDOW
    rows = session.execute(
        select(
            TechnicalEvent.severity,
            TechnicalEvent.subsystem,
            TechnicalEvent.event_code,
            TechnicalEvent.summary,
            TechnicalEvent.details,
            TechnicalEvent.created_at,
            Source.display_name.label("source_name"),
        )
        .outerjoin(Source, Source.id == TechnicalEvent.source_id)
        .where(TechnicalEvent.created_at >= since)
        .order_by(TechnicalEvent.created_at.desc(), TechnicalEvent.id.desc())
        .limit(10)
    ).all()
    return [
        _TechnicalEventSummary(
            severity=row.severity,
            subsystem=row.subsystem,
            event_code=row.event_code,
            summary=row.summary,
            details=row.details,
            source_name=row.source_name,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _load_failing_sources(*, session: Session) -> list[_FailingSourceSummary]:
    rows = session.execute(
        select(
            Source.display_name,
            Source.original_url,
            Source.status,
            Source.consecutive_failures,
            Source.needs_readaptation,
            Source.last_failure_at,
        )
        .where(
            or_(
                Source.status != "ready",
                Source.consecutive_failures > 0,
                Source.needs_readaptation.is_(True),
            )
        )
        .order_by(Source.needs_readaptation.desc(), Source.consecutive_failures.desc(), Source.id.asc())
        .limit(10)
    ).all()
    return [
        _FailingSourceSummary(
            display_name=row.display_name,
            original_url=row.original_url,
            status=row.status,
            consecutive_failures=row.consecutive_failures,
            needs_readaptation=row.needs_readaptation,
            last_failure_at=row.last_failure_at,
        )
        for row in rows
    ]


def _build_grafana_urls(*, grafana_base_url: str) -> tuple[str, str]:
    base_url = grafana_base_url.rstrip("/")
    common_query = urlencode(
        {
            "from": "now-24h",
            "to": "now",
            "viewPanel": _DASHBOARD_PANEL_ID,
            "panelId": _DASHBOARD_PANEL_ID,
            "width": 1200,
            "height": 630,
            "tz": "UTC",
        }
    )
    dashboard_url = f"{base_url}/d/{_DASHBOARD_UID}/{_DASHBOARD_SLUG}?{common_query}"
    render_url = f"{base_url}/render/d-solo/{_DASHBOARD_UID}/{_DASHBOARD_SLUG}?{common_query}"
    return dashboard_url, render_url


def _render_observability_report_email(
    *,
    subject: str,
    now: datetime,
    technical_events: list[_TechnicalEventSummary],
    failing_sources: list[_FailingSourceSummary],
    dashboard_url: str,
    render_url: str,
) -> str:
    warning_count = sum(1 for event in technical_events if event.severity.lower() == "warning")
    error_count = sum(1 for event in technical_events if event.severity.lower() == "error")
    parts = [
        "<html><body>",
        f"<h1>{escape(subject)}</h1>",
        f"<p>{len(technical_events)} technical events in the last 24 hours. "
        f"{warning_count} warning(s), {error_count} error(s).</p>",
        f"<p>{len(failing_sources)} source currently needs operator attention.</p>"
        if len(failing_sources) == 1
        else f"<p>{len(failing_sources)} sources currently need operator attention.</p>",
        f'<p><a href="{escape(dashboard_url, quote=True)}">Open Grafana dashboard</a></p>',
        f'<p><a href="{escape(render_url, quote=True)}">Open Grafana render URL</a></p>',
        f'<p><img src="{escape(render_url, quote=True)}" alt="Grafana observability snapshot for the last 24 hours" /></p>',
        "<h2>Recent technical events</h2>",
        "<ul>",
    ]
    if technical_events:
        for event in technical_events:
            source_name = f" source={escape(event.source_name)}" if event.source_name else ""
            details = f" details={escape(event.details)}" if event.details else ""
            parts.append(
                "<li>"
                f"{escape(_format_datetime(event.created_at))} "
                f"{escape(event.severity.upper())} "
                f"{escape(event.subsystem)}:{escape(event.event_code)} "
                f"{escape(event.summary)}{source_name}{details}"
                "</li>"
            )
    else:
        parts.append("<li>No technical events recorded in the last 24 hours.</li>")
    parts.extend(["</ul>", "<h2>Current source failures</h2>", "<ul>"])
    if failing_sources:
        for source in failing_sources:
            parts.append(
                "<li>"
                f"{escape(source.display_name or source.original_url)} "
                f"status={escape(source.status)} failures={source.consecutive_failures} "
                f"needs_readaptation={'yes' if source.needs_readaptation else 'no'} "
                f"last_failure_at={escape(_format_datetime(source.last_failure_at))}"
                "</li>"
            )
    else:
        parts.append("<li>No active failing sources.</li>")
    parts.extend(
        [
            "</ul>",
            f"<p>Generated at {escape(_format_datetime(now))}.</p>",
            "</body></html>",
        ]
    )
    return "".join(parts)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
