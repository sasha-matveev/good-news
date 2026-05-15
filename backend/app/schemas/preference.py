from __future__ import annotations

from pydantic import BaseModel


class PreferenceFeedbackTotalsResponse(BaseModel):
    total: int
    interesting: int
    want_to_read: int
    not_interesting: int


class PreferenceProfileResponse(BaseModel):
    summary: str
    positive_signals: list[str]
    negative_signals: list[str]
    learning_proof: list[str]
    feedback_totals: PreferenceFeedbackTotalsResponse
