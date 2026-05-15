from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.setting import SecretSetting, Setting


DEFAULT_SETTINGS = {
    "daily_digest_time": "12:00",
    "weekly_digest_day_of_week": "sat",
    "weekly_digest_time": "23:30",
    "recipient_email": None,
    "sender_identity": None,
    "smtp_host": None,
    "smtp_port": "587",
    "smtp_username": None,
    "smtp_security_mode": "starttls",
    "daily_digest_enabled": "true",
    "daily_digest_catch_up_enabled": "true",
    "weekly_digest_enabled": "false",
    "weekly_digest_catch_up_enabled": "true",
}


@dataclass(frozen=True)
class AppSettings:
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


@dataclass(frozen=True)
class AppSettingsUpdate:
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
    smtp_password: str | None


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() == "true"


def _derive_keystream(*, master_key: str, nonce: bytes, length: int) -> bytes:
    seed = hashlib.sha256(master_key.encode("utf-8") + nonce).digest()
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < length:
        blocks.append(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())
        counter += 1
    return b"".join(blocks)[:length]


def encrypt_secret(plaintext: str, master_key: str) -> str:
    plaintext_bytes = plaintext.encode("utf-8")
    nonce = os.urandom(16)
    keystream = _derive_keystream(master_key=master_key, nonce=nonce, length=len(plaintext_bytes))
    ciphertext = bytes(left ^ right for left, right in zip(plaintext_bytes, keystream, strict=True))
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_secret(ciphertext: str, master_key: str) -> str:
    payload = base64.urlsafe_b64decode(ciphertext.encode("utf-8"))
    nonce = payload[:16]
    encrypted_bytes = payload[16:]
    keystream = _derive_keystream(master_key=master_key, nonce=nonce, length=len(encrypted_bytes))
    plaintext = bytes(left ^ right for left, right in zip(encrypted_bytes, keystream, strict=True))
    return plaintext.decode("utf-8")


def load_settings(session: Session) -> AppSettings:
    stored = {row.key: row.value for row in session.execute(select(Setting)).scalars()}
    secret_keys = {row.key for row in session.execute(select(SecretSetting)).scalars()}
    return AppSettings(
        daily_digest_time=stored.get("daily_digest_time") or DEFAULT_SETTINGS["daily_digest_time"],
        weekly_digest_day_of_week=stored.get("weekly_digest_day_of_week")
        or DEFAULT_SETTINGS["weekly_digest_day_of_week"],
        weekly_digest_time=stored.get("weekly_digest_time") or DEFAULT_SETTINGS["weekly_digest_time"],
        recipient_email=stored.get("recipient_email"),
        sender_identity=stored.get("sender_identity"),
        smtp_host=stored.get("smtp_host"),
        smtp_port=int(stored.get("smtp_port") or DEFAULT_SETTINGS["smtp_port"]),
        smtp_username=stored.get("smtp_username"),
        smtp_security_mode=stored.get("smtp_security_mode") or DEFAULT_SETTINGS["smtp_security_mode"],
        daily_digest_enabled=_as_bool(stored.get("daily_digest_enabled"), True),
        daily_digest_catch_up_enabled=_as_bool(stored.get("daily_digest_catch_up_enabled"), True),
        weekly_digest_enabled=_as_bool(stored.get("weekly_digest_enabled"), False),
        weekly_digest_catch_up_enabled=_as_bool(stored.get("weekly_digest_catch_up_enabled"), True),
        smtp_password_configured="smtp_password" in secret_keys,
    )


def _upsert_setting(session: Session, key: str, value: str | None) -> None:
    existing = session.scalar(select(Setting).where(Setting.key == key))
    if existing is None:
        session.add(Setting(key=key, value=value))
        return
    existing.value = value


def _upsert_secret_setting(session: Session, key: str, encrypted_value: str) -> None:
    existing = session.scalar(select(SecretSetting).where(SecretSetting.key == key))
    if existing is None:
        session.add(SecretSetting(key=key, encrypted_value=encrypted_value))
        return
    existing.encrypted_value = encrypted_value


def save_settings(session: Session, payload: AppSettingsUpdate, master_key: str) -> AppSettings:
    _upsert_setting(session, "daily_digest_time", payload.daily_digest_time)
    _upsert_setting(session, "weekly_digest_day_of_week", payload.weekly_digest_day_of_week)
    _upsert_setting(session, "weekly_digest_time", payload.weekly_digest_time)
    _upsert_setting(session, "recipient_email", payload.recipient_email)
    _upsert_setting(session, "sender_identity", payload.sender_identity)
    _upsert_setting(session, "smtp_host", payload.smtp_host)
    _upsert_setting(session, "smtp_port", str(payload.smtp_port))
    _upsert_setting(session, "smtp_username", payload.smtp_username)
    _upsert_setting(session, "smtp_security_mode", payload.smtp_security_mode)
    _upsert_setting(session, "daily_digest_enabled", str(payload.daily_digest_enabled).lower())
    _upsert_setting(session, "daily_digest_catch_up_enabled", str(payload.daily_digest_catch_up_enabled).lower())
    _upsert_setting(session, "weekly_digest_enabled", str(payload.weekly_digest_enabled).lower())
    _upsert_setting(session, "weekly_digest_catch_up_enabled", str(payload.weekly_digest_catch_up_enabled).lower())
    if payload.smtp_password:
        _upsert_secret_setting(session, "smtp_password", encrypt_secret(payload.smtp_password, master_key))
    session.flush()
    return load_settings(session)


def get_smtp_password(session: Session, master_key: str) -> str | None:
    secret_setting = session.scalar(select(SecretSetting).where(SecretSetting.key == "smtp_password"))
    if secret_setting is None:
        return None
    return decrypt_secret(secret_setting.encrypted_value, master_key)


def set_last_daily_digest_sent_at(session: Session, scheduled_for_iso: str) -> None:
    _upsert_setting(session, "last_daily_digest_sent_at", scheduled_for_iso)


def get_last_daily_digest_sent_at(session: Session) -> str | None:
    row = session.scalar(select(Setting).where(Setting.key == "last_daily_digest_sent_at"))
    return row.value if row is not None else None


def set_last_weekly_digest_sent_at(session: Session, scheduled_for_iso: str) -> None:
    _upsert_setting(session, "last_weekly_digest_sent_at", scheduled_for_iso)


def get_last_weekly_digest_sent_at(session: Session) -> str | None:
    row = session.scalar(select(Setting).where(Setting.key == "last_weekly_digest_sent_at"))
    return row.value if row is not None else None


def set_last_observability_report_sent_at(session: Session, scheduled_for_iso: str) -> None:
    _upsert_setting(session, "last_observability_report_sent_at", scheduled_for_iso)


def get_last_observability_report_sent_at(session: Session) -> str | None:
    row = session.scalar(select(Setting).where(Setting.key == "last_observability_report_sent_at"))
    return row.value if row is not None else None
