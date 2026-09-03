"""Where a reply to a Triplet email goes.

Sending from an address needs no mailbox — the domain's DKIM signature is what
authorises it. Receiving a reply does. Without a Reply-To, every reply went to
EMAIL_FROM, so `alerts@yourdomain` had to be a real monitored mailbox or
replies vanished silently. People do reply to fare alerts: to ask something, to
complain, and eventually to make a GDPR request.
"""

import pytest

from app.alerts.email import SMTPEmailProvider, reply_to_header
from app.config import settings

CREDS = dict(smtp_host="smtp.example.com", smtp_username="u", smtp_password="p")


@pytest.fixture()
def email_config(monkeypatch):
    def configure(reply_to: str, **overrides):
        monkeypatch.setattr(settings, "email_from", "alerts@farelin.test")
        monkeypatch.setattr(settings, "email_reply_to", reply_to)
        for key, value in {**CREDS, **overrides}.items():
            monkeypatch.setattr(settings, key, value)

    return configure


def sent_message(monkeypatch):
    """Capture the message the provider would hand to smtplib."""
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            captured["host"] = host

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr("app.alerts.email.smtplib.SMTP", FakeSMTP)
    return captured


# --- The header is set when configured ---------------------------------------

def test_a_configured_reply_to_reaches_the_message(email_config, monkeypatch):
    email_config("hello@farelin.test")
    captured = sent_message(monkeypatch)

    SMTPEmailProvider().send_email("t@example.com", "Confirm", "<p>x</p>", "x")

    message = captured["message"]
    assert message["Reply-To"] == "hello@farelin.test"
    # The sender is unchanged: mail still comes from alerts@, replies go elsewhere.
    assert message["From"] == "alerts@farelin.test"


def test_no_header_when_unset_so_replies_fall_back_to_the_sender(email_config, monkeypatch):
    email_config("")
    captured = sent_message(monkeypatch)

    SMTPEmailProvider().send_email("t@example.com", "Confirm", "<p>x</p>", "x")

    assert captured["message"]["Reply-To"] is None


def test_surrounding_whitespace_is_tolerated(email_config):
    email_config("  hello@farelin.test\t")
    assert reply_to_header() == "hello@farelin.test"


# --- A broken value must not ship --------------------------------------------

@pytest.mark.parametrize(
    "value",
    ["notanemail", "@farelin.test", "hello@", "hello@localhost", "hello"],
)
def test_an_address_that_is_not_one_is_ignored(email_config, value):
    """Ignored rather than sent.

    Some receivers read a malformed header as a spam signal, and that cost
    lands on every message Triplet sends — not just on the reply nobody could
    make. Falling back to EMAIL_FROM is the smaller failure.
    """
    email_config(value)
    assert reply_to_header() is None


@pytest.mark.parametrize(
    "value",
    [
        "hello@farelin.test\r\nBcc: attacker@example.com",
        "hello@farelin.test\nSubject: injected",
    ],
)
def test_a_line_break_cannot_inject_extra_headers(email_config, value):
    """A configuration value is not a place to smuggle headers from."""
    email_config(value)
    assert reply_to_header() is None


def test_a_broken_value_is_reported(email_config, caplog):
    import logging

    email_config("notanemail")
    with caplog.at_level(logging.ERROR):
        reply_to_header()

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "EMAIL_REPLY_TO" in logged


# --- The console provider must rehearse the same thing -----------------------

def test_the_console_provider_reports_the_same_reply_to(email_config, caplog):
    """A console provider that differs from the real one is a poor rehearsal."""
    import logging

    from app.alerts.email import ConsoleEmailProvider

    email_config("hello@farelin.test")
    with caplog.at_level(logging.INFO):
        ConsoleEmailProvider().send_email("t@example.com", "Confirm", "<p>x</p>", "x")

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "hello@farelin.test" in logged
