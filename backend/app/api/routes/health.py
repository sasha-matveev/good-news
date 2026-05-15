from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.schema_guard import SchemaNotReadyError, assert_database_schema_is_current

router = APIRouter()


@router.get("/health")
def health_check(request: Request) -> dict[str, str]:
    session_factory = request.app.state.session_factory

    try:
        assert_database_schema_is_current(session_factory)
    except SchemaNotReadyError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": "database schema is not at head"},
        )

    return {"status": "ok"}
