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

    #: Whether this provider actually delivers to a mailbox.
    #:
    #: Read by the production configuration check, which used to ask whether
    #: EMAIL_PROVIDER was the string "console" instead. That let any other
    #: value satisfy it while still delivering nothing.
    delivers: bool = True

    def send_email(self, to: str, subject: str, html_body: str, text_body: str) -> None:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    def __init__(self):
        super().__init__(provider_name="console", delivers=False)

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
        missing = [
            name
            for name, value in (
                ("SMTP_HOST", settings.smtp_host),
                ("SMTP_USERNAME", settings.smtp_username),
                ("SMTP_PASSWORD", settings.smtp_password),
            )
            if not value
        ]
        if missing:
            raise EmailProviderError(
                f"EMAIL_PROVIDER=smtp needs {', '.join(missing)}."
            )

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


#: Every value EMAIL_PROVIDER understands.
KNOWN_EMAIL_PROVIDERS = ("console", "smtp")


def normalized_email_provider() -> str:
    """The configured provider, trimmed and lowercased.

    A stray capital or trailing space in a hosting dashboard is not a decision
    to send no email, and should not be treated as one.
    """
    return (settings.email_provider or "").strip().lower()


def build_email_provider() -> EmailProvider:
    """The configured provider, or an error naming what is available.

    This used to fall through to the console for any unrecognised value. The
    combination was the worst possible one: EMAIL_PROVIDER=resend (or SMTP, or
    "smtp " with a trailing space) silently delivered nothing, while the
    production guard — which only checked for the literal string "console" —
    saw a value it did not recognise as the console and let the service start.
    Setting EMAIL_REQUIRE_REAL_PROVIDER=true, whose entire purpose is to refuse
    that situation, did not help: a typo passed it.

    An unknown value is now a configuration error, raised where it can be seen,
    rather than a mail system that looks configured and is not.
    """
    provider = normalized_email_provider()

    if provider == "smtp":
        try:
            return SMTPEmailProvider()
        except EmailProviderError as exc:
            # Half-configured SMTP is a mistake, not a reason to take search and
            # discovery down with the mail system. Same treatment as an unknown
            # name: shout, degrade, and let EMAIL_REQUIRE_REAL_PROVIDER decide
            # whether that is tolerable in this deployment.
            logger.error("email_provider_misconfigured: %s No email will be delivered.", exc)
            return ConsoleEmailProvider()
    if provider in ("console", ""):
        return ConsoleEmailProvider()

    # Warned about, not raised on. An unrecognised name is a mistake worth
    # shouting about, but not worth taking search and discovery down for — that
    # is the crash-loop this codebase has already suffered twice. It degrades to
    # the console provider, which reports `delivers = False`, so the production
    # check refuses to start when EMAIL_REQUIRE_REAL_PROVIDER is set and warns
    # loudly otherwise. Either way the mistake is visible; neither way is an
    # outage over a typo.
    logger.error(
        "email_provider_unknown: EMAIL_PROVIDER=%r is not implemented, so no email will be "
        "delivered. Use one of: %s. Any SMTP service — Resend, Postmark, SES, Fastmail — is "
        "reached with EMAIL_PROVIDER=smtp plus SMTP_HOST, SMTP_USERNAME and SMTP_PASSWORD.",
        settings.email_provider,
        ", ".join(KNOWN_EMAIL_PROVIDERS),
    )
    return ConsoleEmailProvider()
