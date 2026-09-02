import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


class EmailProviderError(RuntimeError):
    pass


@dataclass
class EmailProvider:
    provider_name: str

    def send_email(self, to: str, subject: str, html_body: str, text_body: str) -> None:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    def __init__(self):
        super().__init__(provider_name="console")

    def send_email(self, to: str, subject: str, html_body: str, text_body: str) -> None:
        logger.info("console_email to=%s subject=%s\n%s", to, subject, text_body)
        # Through the logger rather than print, so the same redaction every
        # other line gets applies here too. The body of a Triplet email
        # routinely contains a single-use token, and print() bypasses all of it.
        logger.info(
            "console_email_sent",
            extra={"event": "email.console", "to": to, "subject": subject, "body": text_body},
        )


class SMTPEmailProvider(EmailProvider):
    def __init__(self):
        super().__init__(provider_name="smtp")
        if not settings.smtp_host:
            raise EmailProviderError("SMTP_HOST is required when EMAIL_PROVIDER=smtp.")

    def send_email(self, to: str, subject: str, html_body: str, text_body: str) -> None:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)


def build_email_provider() -> EmailProvider:
    if settings.email_provider == "smtp":
        return SMTPEmailProvider()
    return ConsoleEmailProvider()
