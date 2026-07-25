from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.digests import router as digests_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.health import router as health_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.preferences import router as preferences_router
from app.api.routes.posts import router as posts_router
from app.api.routes.settings import router as settings_router
from app.api.routes.sources import router as sources_router
from app.api.routes.want_to_read import router as want_to_read_router
from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory
from app.core.observability import instrument_app
from app.core.schema_guard import assert_database_schema_is_current


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    discovery_responses: dict[str, str] | None = None,
    now_provider: callable | None = None,
    source_ingestion_client_factory: callable | None = None,
    delivery_service_client_factory: callable | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    app = FastAPI(title="Good News Content API Service")
    app.state.discovery_responses = discovery_responses or {}
    app.state.session_factory = session_factory
    app.state.now_provider = now_provider or resolved_settings.now
    app.state.settings = resolved_settings
    app.state.source_ingestion_client_factory = source_ingestion_client_factory
    app.state.delivery_service_client_factory = delivery_service_client_factory
    instrument_app(app=app, service_name="content-api-service")

    app.include_router(feedback_router, prefix="/api")
    app.include_router(digests_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(monitoring_router, prefix="/api")
    app.include_router(preferences_router, prefix="/api")
    app.include_router(posts_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(sources_router, prefix="/api")
    app.include_router(want_to_read_router, prefix="/api")

    @app.on_event("startup")
    def ensure_session_factory() -> None:
        if app.state.session_factory is None:
            engine = create_engine_from_settings(settings=resolved_settings)
            app.state.session_factory = create_session_factory(engine)
        assert_database_schema_is_current(app.state.session_factory)

    return app


app = create_app()
