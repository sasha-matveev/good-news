from __future__ import annotations

import pytest

from app.services.email_service import EmailMessage, EmailSendError, send_email


class RecordingTransport:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        if self.should_fail:
            raise RuntimeError("smtp offline")
        self.calls.append(message)


def test_send_email_delegates_to_transport() -> None:
    transport = RecordingTransport()

    send_email(
        EmailMessage(
            sender="Good News Digest <digest@example.com>",
            recipient="reader@example.com",
            subject="Digest",
            html_body="<p>Hello</p>",
        ),
        transport=transport,
    )

    assert transport.calls == [
        EmailMessage(
            sender="Good News Digest <digest@example.com>",
            recipient="reader@example.com",
            subject="Digest",
            html_body="<p>Hello</p>",
        )
    ]


def test_send_email_wraps_transport_failures() -> None:
    with pytest.raises(EmailSendError, match="smtp offline"):
        send_email(
            EmailMessage(
                sender="Good News Digest <digest@example.com>",
                recipient="reader@example.com",
                subject="Digest",
                html_body="<p>Hello</p>",
            ),
            transport=RecordingTransport(should_fail=True),
        )
