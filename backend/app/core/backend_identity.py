from __future__ import annotations

import re
import uuid

from fastapi import FastAPI, Request

BACKEND_HEADER = "X-Good-News-Backend"
CORRELATION_HEADER = "X-Correlation-ID"
BACKEND_IDENTITY = "python"
_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def install_backend_identity(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_backend_identity(request: Request, call_next):
        correlation_id = _correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[BACKEND_HEADER] = BACKEND_IDENTITY
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


def _correlation_id(candidate: str | None) -> str:
    normalized = (candidate or "").strip()
    if _CORRELATION_ID_PATTERN.fullmatch(normalized):
        return normalized
    return str(uuid.uuid4())
