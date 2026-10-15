"""Outgoing email. Reminders only, and only for users who opted in. No sensitive content in the body."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings

log = logging.getLogger("app.email")


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class LogEmailSender:
    """Development default: writes the email to the log instead of sending it."""

    async def send(self, to: str, subject: str, body: str) -> None:
        log.info(
            "email (not sent: no SMTP configured)",
            extra={"subject": subject, "to_domain": to.split("@")[-1]},
        )


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        sender: str,
        starttls: bool,
    ) -> None:
        self._host, self._port, self._username, self._password = host, port, username, password
        self._sender, self._starttls = sender, starttls

    def _send_sync(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self._sender, to, subject
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=15) as client:
            if self._starttls:
                client.starttls()
            if self._username and self._password:
                client.login(self._username, self._password)
            client.send_message(message)

    async def send(self, to: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, body)


_sender: EmailSender | None = None


def get_email_sender() -> EmailSender:
    global _sender
    if _sender is None:
        s = get_settings()
        if s.smtp_host:
            _sender = SmtpEmailSender(
                s.smtp_host,
                s.smtp_port,
                s.smtp_username,
                s.smtp_password.get_secret_value() if s.smtp_password else None,
                s.email_from,
                s.smtp_starttls,
            )
        else:
            _sender = LogEmailSender()
    return _sender


def set_email_sender(sender: EmailSender | None) -> None:
    global _sender
    _sender = sender
