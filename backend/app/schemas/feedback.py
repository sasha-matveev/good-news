from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

FeedbackState = Literal["interesting", "not_interesting", "want_to_read", "norm"]


class FeedbackUpdateRequest(BaseModel):
    state: FeedbackState


class FeedbackResponse(BaseModel):
    post_id: int
    state: FeedbackState
