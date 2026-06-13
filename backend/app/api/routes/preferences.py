from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.schemas.preference import PreferenceProfileResponse
from app.services.preferences import build_preference_profile, persist_preference_profile

router = APIRouter(tags=["preferences"])


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_session(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Generator[Session, None, None]:
    with session_scope(session_factory) as session:
        yield session


def _recompute_and_respond(session: Session) -> PreferenceProfileResponse:
    profile = build_preference_profile(session)
    persist_preference_profile(session, profile)
    return PreferenceProfileResponse(
        summary=profile.summary,
        positive_signals=profile.positive_signals,
        negative_signals=profile.negative_signals,
        learning_proof=profile.learning_proof,
        feedback_totals=profile.feedback_totals,
    )


@router.get("/preferences", response_model=PreferenceProfileResponse)
def get_preferences(session: Session = Depends(get_session)) -> PreferenceProfileResponse:
    return _recompute_and_respond(session)


@router.post("/preferences/recompute", response_model=PreferenceProfileResponse)
def recompute_preferences(session: Session = Depends(get_session)) -> PreferenceProfileResponse:
    """Rebuild the preference profile from current reactions + post analysis."""
    return _recompute_and_respond(session)
