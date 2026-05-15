from __future__ import annotations

from dataclasses import dataclass
import smtplib
from typing import Protocol

from email.mime.text import MIMEText


class EmailSendError(RuntimeError):
    """Raised when email delivery fails."""


@dataclass(frozen=True)
class EmailMessage:
    sender: str
    recipient: str
    subject: str
    html_body: str


class EmailTransport(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpTransport:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        security_mode: str,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.security_mode = security_mode

    def send(self, message: EmailMessage) -> None:
        mime = MIMEText(message.html_body, "html", "utf-8")
        mime["Subject"] = message.subject
        mime["From"] = message.sender
        mime["To"] = message.recipient

        if self.security_mode == "ssl":
            server = smtplib.SMTP_SSL(self.host, self.port)
        else:
            server = smtplib.SMTP(self.host, self.port)
        with server:
            if self.security_mode == "starttls":
                server.starttls()
            if self.username:
                server.login(self.username, self.password or "")
            server.sendmail(message.sender, [message.recipient], mime.as_string())


def send_email(message: EmailMessage, *, transport: EmailTransport) -> None:
    try:
        transport.send(message)
    except Exception as exc:  # pragma: no cover
        raise EmailSendError(str(exc)) from exc
