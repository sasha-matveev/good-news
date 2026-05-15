from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.email_service import EmailMessage, EmailSendError, send_email
from app.services.settings_service import get_smtp_password, load_settings


DELIVERY_OWNED_SETTING_KEYS = {
    "recipient_email",
    "sender_identity",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_security_mode",
    "smtp_password",
    "daily_digest_enabled",
    "daily_digest_catch_up_enabled",
    "last_daily_digest_sent_at",
}
def send_test_email_command(
    *,
    session: Session,
    runtime_settings: Settings | None = None,
    email_transport: object | None = None,
    app_master_key: str | None = None,
) -> None:
    """Explicit delivery-domain SMTP test execution behind the delivery boundary."""

    resolved_runtime_settings = runtime_settings or Settings.from_env()
    settings = load_settings(session)
    transport = email_transport
    if transport is None:
        from app.services.email_service import SmtpTransport

        master_key = app_master_key or resolved_runtime_settings.app_master_key()
        transport = SmtpTransport(
            host=settings.smtp_host or "",
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=get_smtp_password(session, master_key),
            security_mode=settings.smtp_security_mode,
        )

    if not settings.recipient_email or not settings.sender_identity:
        raise EmailSendError("Missing recipient_email or sender_identity")

    message = EmailMessage(
        sender=settings.sender_identity,
        recipient=settings.recipient_email,
        subject="Good News digest SMTP test",
        html_body="<p>SMTP settings look ready.</p>",
    )
    send_email(message, transport=transport)
