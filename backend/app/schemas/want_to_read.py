from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WantToReadUpdateRequest(BaseModel):
    saved: bool


class WantToReadUpdateResponse(BaseModel):
    post_id: int
    saved: bool
    feedback_state: Literal["interesting", "not_interesting", "want_to_read"] | None
