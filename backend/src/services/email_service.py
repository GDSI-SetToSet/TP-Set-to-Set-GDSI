import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from backend.src.core.config import (
    EMAIL_BACKEND,
    EMAIL_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Registra el correo en el log del backend en lugar de enviarlo (desarrollo y pruebas)."""

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning("Correo para %s | %s\n%s", to, subject, body)


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.sender = sender
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)


def build_email_sender(backend: str = EMAIL_BACKEND) -> EmailSender:
    if backend == "smtp":
        return SmtpEmailSender(SMTP_HOST or "", SMTP_PORT, EMAIL_FROM, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS)
    return ConsoleEmailSender()
