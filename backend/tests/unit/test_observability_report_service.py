from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import create_engine_from_url, create_session_factory, session_scope
from app.models.base import Base
from app.models.digest import Digest
from app.models.setting import TechnicalEvent
from app.models.source import Source
from app.services.observability_report_service import generate_daily_observability_report


def test_generate_daily_observability_report_persists_operator_digest_with_grafana_links() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 4, 26, 18, 0, tzinfo=UTC)

    with session_scope(session_factory) as session:
        session.add(
            Source(
                id=1,
                display_name="Alpha",
                original_url="https://alpha.example",
                status="failing",
                consecutive_failures=2,
                last_failure_at=now - timedelta(hours=2),
                needs_readaptation=True,
                readaptation_reason="sync failed twice",
            )
        )
        session.add(
            Source(
                id=2,
                display_name="Beta",
                original_url="https://beta.example",
                status="ready",
                consecutive_failures=0,
            )
        )
        session.add_all(
            [
                TechnicalEvent(
                    severity="warning",
                    subsystem="source-sync",
                    event_code="source.repeated_failure",
                    summary="Source sync hit the repeated-failure threshold.",
                    details="Alpha feed returned HTTP 500",
                    source_id=1,
                    created_at=now - timedelta(hours=1),
                ),
                TechnicalEvent(
                    severity="warning",
                    subsystem="analysis",
                    event_code="analysis.write_failed",
                    summary="Post analysis write failed.",
                    details="timeout",
                    source_id=1,
                    created_at=now - timedelta(minutes=30),
                ),
                TechnicalEvent(
                    severity="info",
                    subsystem="source-sync",
                    event_code="source.recovered",
                    summary="Recovered.",
                    details=None,
                    source_id=2,
                    created_at=now - timedelta(days=2),
                ),
            ]
        )

    with session_scope(session_factory) as session:
        report = generate_daily_observability_report(
            session=session,
            now=now,
            grafana_base_url="https://grafana.good-news.example",
        )
        stored_digest = session.get(Digest, report.digest_id)

    assert report.digest_id > 0
    assert report.item_count == 2
    assert "2 technical events in the last 24 hours" in report.html_body
    assert "1 source currently needs operator attention" in report.html_body
    assert "https://grafana.good-news.example/d/good-news-overview" in report.html_body
    assert "https://grafana.good-news.example/render/d-solo/good-news-overview" in report.html_body
    assert stored_digest is not None
    assert stored_digest.digest_type == "observability_daily"
    assert stored_digest.status == "generated"
    assert stored_digest.recipient_email is None
    metadata = json.loads(stored_digest.metadata_json or "{}")
    assert metadata["dashboard_url"].startswith("https://grafana.good-news.example/d/good-news-overview")
    assert metadata["render_url"].startswith("https://grafana.good-news.example/render/d-solo/good-news-overview")

    persisted_types = session.execute(select(Digest.digest_type).order_by(Digest.id)).scalars().all()
    assert persisted_types == ["observability_daily"]
