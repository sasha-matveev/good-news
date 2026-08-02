from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SettingsResponse(BaseModel):
    daily_digest_time: str
    weekly_digest_day_of_week: str
    weekly_digest_time: str
    recipient_email: str | None
    sender_identity: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_security_mode: str
    daily_digest_enabled: bool
    daily_digest_catch_up_enabled: bool
    weekly_digest_enabled: bool
    weekly_digest_catch_up_enabled: bool
    smtp_password_configured: bool
    analysis_summary_prompt: str
    analysis_verdict_reason_prompt: str


class SettingsUpdateRequest(BaseModel):
    daily_digest_time: str
    weekly_digest_day_of_week: str
    weekly_digest_time: str
    recipient_email: str | None = None
    sender_identity: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(ge=1, le=65535)
    smtp_username: str | None = None
    smtp_security_mode: str
    daily_digest_enabled: bool = True
    daily_digest_catch_up_enabled: bool = True
    weekly_digest_enabled: bool = False
    weekly_digest_catch_up_enabled: bool = True
    smtp_password: str | None = None
    # Editable analysis instruction texts. Default to "" so older clients that
    # omit them still validate; blank input is treated as "reset to default" by
    # the settings service.
    analysis_summary_prompt: str = ""
    analysis_verdict_reason_prompt: str = ""

    @field_validator("analysis_summary_prompt", "analysis_verdict_reason_prompt")
    @classmethod
    def validate_prompt_length(cls, value: str) -> str:
        # Lenient cap to avoid pathological payloads; admin-authored text only.
        if len(value) > 8000:
            raise ValueError("prompt must be at most 8000 characters")
        return value

    @field_validator("daily_digest_time", "weekly_digest_time")
    @classmethod
    def validate_digest_time(cls, value: str, info) -> str:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError(f"{info.field_name} must use HH:MM format")
        hour, minute = parts
        if not (hour.isdigit() and minute.isdigit()):
            raise ValueError(f"{info.field_name} must use HH:MM format")
        parsed_hour = int(hour)
        parsed_minute = int(minute)
        if parsed_hour not in range(24) or parsed_minute not in range(60):
            raise ValueError(f"{info.field_name} must use HH:MM format")
        return f"{parsed_hour:02d}:{parsed_minute:02d}"

    @field_validator("weekly_digest_day_of_week")
    @classmethod
    def validate_weekly_digest_day_of_week(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
            raise ValueError("weekly_digest_day_of_week must be one of mon, tue, wed, thu, fri, sat, sun")
        return normalized

    @field_validator("smtp_security_mode")
    @classmethod
    def validate_smtp_security_mode(cls, value: str) -> str:
        if value not in {"none", "starttls", "ssl"}:
            raise ValueError("smtp_security_mode must be one of none, starttls, ssl")
        return value
