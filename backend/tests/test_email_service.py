import logging
from typing import ClassVar

from backend.src.services import email_service
from backend.src.services.email_service import (
    ConsoleEmailSender,
    SmtpEmailSender,
    build_email_sender,
)


class FakeSmtp:
    instances: ClassVar[list["FakeSmtp"]] = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.calls = []
        self.sent = []
        FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message):
        self.sent.append(message)


def test_console_sender_logs_message(caplog):
    with caplog.at_level(logging.WARNING, logger=email_service.__name__):
        ConsoleEmailSender().send("user@example.com", "Asunto", "https://link?token=abc")
    assert "user@example.com" in caplog.text
    assert "https://link?token=abc" in caplog.text


def test_smtp_sender_uses_tls_login_and_sends(monkeypatch):
    FakeSmtp.instances.clear()
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSmtp)
    sender = SmtpEmailSender("smtp.example.com", 2525, "Set to Set <no-reply@example.com>", "user", "secret")
    sender.send("user@example.com", "Asunto", "Cuerpo")
    smtp = FakeSmtp.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.example.com", 2525)
    assert smtp.calls == ["starttls", ("login", "user", "secret")]
    message = smtp.sent[0]
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Asunto"
    assert message.get_content().strip() == "Cuerpo"


def test_smtp_sender_without_tls_or_credentials(monkeypatch):
    FakeSmtp.instances.clear()
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSmtp)
    SmtpEmailSender("localhost", 1025, "no-reply@example.com", use_tls=False).send("a@example.com", "S", "B")
    assert FakeSmtp.instances[0].calls == []
    assert len(FakeSmtp.instances[0].sent) == 1


def test_build_email_sender_selects_backend():
    assert isinstance(build_email_sender("console"), ConsoleEmailSender)
    assert isinstance(build_email_sender("smtp"), SmtpEmailSender)
