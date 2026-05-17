from __future__ import annotations

import urllib.request
import urllib.error
from datetime import datetime

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.db import session_scope
from app.models.post import Post
from app.models.post_analysis import PostAnalysis
from app.models.source import Source

router = APIRouter(tags=["monitoring"])

_SERVICE_TIMEOUT = 2


def _check_health(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=_SERVICE_TIMEOUT) as resp:
            return "ok" if resp.status == 200 else "error"
    except Exception:
        return "error"


def _build_service_health(settings: Settings, *, is_monolith: bool) -> dict[str, str]:
    # Monolith: all four former services run in the same process.
    if is_monolith:
        return {
            "content_api": "ok",
            "analysis_llm": "ok",
            "source_ingestion": "ok",
            "delivery": "ok",
        }
    return {
        "content_api": "ok",  # we are the content API — if this code runs, it's up
        "analysis_llm": _check_health(
            f"http://{settings.analysis_service_host}:{settings.analysis_service_port}/health"
        ),
        "source_ingestion": _check_health(
            f"http://{settings.source_ingestion_service_host}:{settings.source_ingestion_service_port}/health"
        ),
        "delivery": _check_health(
            f"http://{settings.delivery_service_host}:{settings.delivery_service_port}/health"
        ),
    }


def _build_summary(session: Session, settings: Settings, *, is_monolith: bool) -> dict:
    sources_active: int = session.scalar(
        select(func.count()).select_from(Source).where(Source.active.is_(True))
    ) or 0

    sources_total: int = session.scalar(
        select(func.count()).select_from(Source)
    ) or 0

    posts_total: int = session.scalar(
        select(func.count()).select_from(Post)
    ) or 0

    posts_unranked: int = session.scalar(
        select(func.count())
        .select_from(Post)
        .outerjoin(PostAnalysis, PostAnalysis.post_id == Post.id)
        .where(PostAnalysis.id.is_(None))
    ) or 0

    last_sync_at: datetime | None = session.scalar(
        select(func.max(Source.last_success_at))
    )

    last_sync_str: str | None = None
    if last_sync_at is not None:
        iso = last_sync_at.isoformat()
        last_sync_str = iso.replace("+00:00", "Z") if "+" in iso or iso.endswith("Z") else iso + "Z"

    return {
        "sources_active": sources_active,
        "sources_total": sources_total,
        "posts_total": posts_total,
        "posts_unranked": posts_unranked,
        "last_sync_at": last_sync_str,
        "services": _build_service_health(settings, is_monolith=is_monolith),
    }


@router.get("/monitoring/summary")
def monitoring_summary(request: Request) -> dict:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    settings: Settings = request.app.state.settings
    is_monolith = getattr(request.app.state, "analysis_client_factory", None) is not None
    with session_scope(session_factory) as session:
        return _build_summary(session, settings, is_monolith=is_monolith)


@router.get("/monitoring/queue")
def analysis_queue(request: Request) -> list[dict]:
    """Return posts that are pending LLM analysis (no PostAnalysis row yet)."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_scope(session_factory) as session:
        rows = session.execute(
            select(Post.id, Post.title, Post.source_id, Post.created_at)
            .outerjoin(PostAnalysis, PostAnalysis.post_id == Post.id)
            .where(PostAnalysis.id.is_(None))
            .order_by(Post.created_at)
            .limit(100)
        ).all()

        source_names: dict[int, str | None] = {}
        for row in rows:
            if row.source_id not in source_names:
                src = session.get(Source, row.source_id)
                source_names[row.source_id] = (src.display_name or src.original_url) if src else None

        result = []
        for row in rows:
            created_str: str | None = None
            if row.created_at is not None:
                iso = row.created_at.isoformat()
                created_str = iso.replace("+00:00", "Z") if "+" in iso or iso.endswith("Z") else iso + "Z"
            result.append({
                "post_id": row.id,
                "title": row.title,
                "source_name": source_names.get(row.source_id),
                "created_at": created_str,
            })
        return result
