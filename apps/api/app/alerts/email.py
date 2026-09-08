import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmailProviderError(RuntimeError):
    pass


def sender_address() -> str:
    """Return one validated mailbox address from EMAIL_FROM.

    The public display name comes from APP_NAME, never from an untrusted header
    fragment in configuration. This prevents CR/LF header injection while still
    allowing the SMTP envelope to use the verified Farelin domain.
    """
    value = (settings.email_from or "").strip()
    if any(ch in value for ch in "\r\n"):
        raise EmailProviderError("EMAIL_FROM contains a line break.")
    _, address = parseaddr(value)
    local, separator, domain = address.partition("@")
    if value != address or not local or separator != "@" or not domain or "." not in domain:
        raise EmailProviderError("EMAIL_FROM must contain one valid email address.")
    return address


def sender_header() -> str:
    """The safe public From header, e.g. ``Farelin <alerts@farelin.com>``."""
    display_name = (settings.app_name or "Farelin").strip()
    if any(ch in display_name for ch in "\r\n"):
        raise EmailProviderError("APP_NAME contains a line break.")
    return formataddr((display_name, sender_address()))


def reply_to_header() -> str | None:
    """The Reply-To address, when one is configured and usable.

    Validated rather than passed through. A malformed Reply-To is worse than
    none at all: some receivers treat a broken header as a spam signal, and
    that cost lands on the deliverability of every message Triplet sends, not
    just on the one reply nobody could make.

    The check is deliberately shallow — one address, containing an @, with
    something either side and no header-injection characters. Anything more
    elaborate would reject valid addresses, which is the more common mistake.
    """
    value = (settings.email_reply_to or "").strip()
    if not value:
        return None

    # A newline here would let a configuration value inject extra headers.
    if any(ch in value for ch in "\r\n"):
        logger.error("email_reply_to_invalid: EMAIL_REPLY_TO contains a line break; ignoring it.")
        return None

    local, _, domain = value.partition("@")
    if not local or not domain or "." not in domain:
        logger.error(
            "email_reply_to_invalid: EMAIL_REPLY_TO=%r is not an address; ignoring it so replies "
            "fall back to EMAIL_FROM.",
            value,
        )
        return None

    return value


def contact_recipient() -> str | None:
    """Return the monitored support inbox without exposing it publicly.

    CONTACT_EMAIL_TO wins. EMAIL_REPLY_TO is a useful fallback because it is
    already required to be an inbox a person reads. EMAIL_FROM is deliberately
    not a fallback: authenticated sender addresses often have no mailbox.
    """
    value = (settings.contact_email_to or "").strip()
    if not value:
        return reply_to_header()
    if any(ch in value for ch in "\r\n"):
        logger.error("contact_email_invalid: CONTACT_EMAIL_TO contains a line break.")
        return None
    _, address = parseaddr(value)
    local, separator, domain = address.partition("@")
    if value != address or not local or separator != "@" or not domain or "." not in domain:
        logger.error("contact_email_invalid: CONTACT_EMAIL_TO is not one valid address.")
        return None
    return address


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
        # Reports the same headers the SMTP provider would set, so what someone
        # sees locally matches what a recipient would get. A console provider
        # that quietly differs from the real one is a poor rehearsal.
        reply_to = reply_to_header()
        try:
            from_header = sender_header()
        except EmailProviderError:
            from_header = "invalid EMAIL_FROM"
        logger.info(
            "console_email to=%s reply_to=%s subject=%s\n%s",
            to,
            reply_to or from_header,
            subject,
            text_body,
        )
        # Through the logger rather than print, so the same redaction every
        # other line gets applies here too. The body of a Triplet email
        # routinely contains a single-use token, and print() bypasses all of it.
        logger.info(
            "console_email_sent",
            extra={
                "event": "email.console",
                "to": to,
                "replyTo": reply_to,
                "subject": subject,
                "body": text_body,
            },
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
        # Validate headers while resolving readiness, not after a watch has
        # already spent its notification slot attempting delivery.
        sender_header()

    def send_email(self, to: str, subject: str, html_body: str, text_body: str) -> None:
        message = EmailMessage()
        message["From"] = sender_header()
        message["To"] = to
        message["Subject"] = subject
        reply_to = reply_to_header()
        if reply_to:
            message["Reply-To"] = reply_to
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)


class ResendEmailProvider(EmailProvider):
    """Deliver through Resend's HTTPS API.

    Railway blocks outbound SMTP on several plans. HTTPS uses the same
    transactional provider without depending on mail ports, and gives every
    caller the same EmailProvider contract as SMTP.
    """

    endpoint = "https://api.resend.com/emails"

    def __init__(self):
        super().__init__(provider_name="resend")
        if not settings.resend_api_key:
            raise EmailProviderError("EMAIL_PROVIDER=resend needs RESEND_API_KEY.")
        sender_header()

    def send_email(self, to: str, subject: str, html_body: str, text_body: str) -> None:
        payload: dict[str, object] = {
            "from": sender_header(),
            "to": [to],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }
        reply_to = reply_to_header()
        if reply_to:
            payload["reply_to"] = reply_to

        try:
            response = httpx.post(
                self.endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "User-Agent": "Farelin/1.0",
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise EmailProviderError("The Resend API could not be reached.") from exc
        if response.status_code not in {200, 201}:
            # Never include the response body: provider errors can echo an
            # address or other message data into logs and public API responses.
            raise EmailProviderError(
                f"The Resend API rejected the message (HTTP {response.status_code})."
            )


#: Every value EMAIL_PROVIDER understands.
KNOWN_EMAIL_PROVIDERS = ("console", "resend", "smtp")


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

    if provider == "resend":
        try:
            return ResendEmailProvider()
        except EmailProviderError as exc:
            logger.error("email_provider_misconfigured: %s No email will be delivered.", exc)
            return ConsoleEmailProvider()
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
        "delivered. Use one of: %s. Resend is reached over HTTPS with "
        "EMAIL_PROVIDER=resend plus RESEND_API_KEY; other mail services can use SMTP.",
        settings.email_provider,
        ", ".join(KNOWN_EMAIL_PROVIDERS),
    )
    return ConsoleEmailProvider()


def safe_email_status() -> dict[str, object]:
    """Operational readiness without credentials or mailbox-local parts."""
    provider = build_email_provider()
    try:
        domain = sender_address().rsplit("@", 1)[1]
    except EmailProviderError:
        domain = None
    return {
        "provider": provider.provider_name,
        "configured": provider.delivers,
        "delivers": provider.delivers,
        "fromDomain": domain,
        "replyToConfigured": reply_to_header() is not None,
        "contactRecipientConfigured": contact_recipient() is not None,
    }
