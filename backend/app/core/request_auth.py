from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from app.core.config import Settings

logger = logging.getLogger(__name__)

TokenVerifier = Callable[[str], dict]

_EXEMPT_PATH_PREFIXES = ("/api/health", "/internal/")


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip() or None


def firebase_token_verifier(project_id: str) -> TokenVerifier:
    """Build a verifier for Firebase Auth ID tokens issued for *project_id*."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    transport = google_requests.Request()

    def verify(token: str) -> dict:
        return google_id_token.verify_firebase_token(token, transport, audience=project_id)

    return verify


def google_oidc_token_verifier(audience: str | None) -> TokenVerifier:
    """Build a verifier for Google-signed OIDC tokens (Cloud Scheduler service accounts)."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    transport = google_requests.Request()

    def verify(token: str) -> dict:
        return google_id_token.verify_oauth2_token(token, transport, audience=audience)

    return verify


def install_user_auth_middleware(
    app: FastAPI,
    settings: Settings,
    verifier: TokenVerifier | None = None,
) -> None:
    """Require a Firebase ID token from an allowlisted email on every /api route.

    Installed only when GOOD_NEWS_FIREBASE_PROJECT_ID is configured;
    /api/health and /internal/* (OIDC-protected separately) are exempt.
    """
    if not settings.firebase_project_id:
        return

    allowed_emails = settings.allowed_email_set()
    if verifier is not None:
        app.state.user_token_verifier = verifier

    def _resolve_verifier() -> TokenVerifier:
        resolved = getattr(app.state, "user_token_verifier", None)
        if resolved is None:
            resolved = firebase_token_verifier(settings.firebase_project_id)
            app.state.user_token_verifier = resolved
        return resolved

    @app.middleware("http")
    async def require_authenticated_user(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _EXEMPT_PATH_PREFIXES):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        token = _bearer_token(request)
        if token is None:
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token."})
        try:
            claims = _resolve_verifier()(token)
        except Exception:
            logger.warning("Rejected request with invalid Firebase token for %s", path)
            return JSONResponse(status_code=401, content={"detail": "Invalid token."})

        email = str(claims.get("email", "")).lower()
        if not claims.get("email_verified") or email not in allowed_emails:
            logger.warning("Rejected request from non-allowlisted email %s for %s", email, path)
            return JSONResponse(status_code=403, content={"detail": "Not allowed."})

        return await call_next(request)
