"""Which provider a configuration actually gets, and whether it delivers.

EMAIL_PROVIDER is a free-form string from a hosting dashboard. It used to be
compared literally: anything that was not exactly "smtp" fell through to the
console, and the production guard only objected to the exact word "console".

So EMAIL_PROVIDER=SMTP, or "smtp " with a trailing space, or a provider name
Triplet does not implement, all delivered nothing while satisfying
EMAIL_REQUIRE_REAL_PROVIDER=true — the flag whose entire purpose is to refuse
that situation.

The other half of these tests holds the opposite line: a mail misconfiguration
must never take search and discovery down with it. That has happened twice.
"""

import pytest

from app.alerts.email import (
    ConsoleEmailProvider,
    SMTPEmailProvider,
    build_email_provider,
    normalized_email_provider,
)
from app.config import settings


@pytest.fixture()
def email_settings(monkeypatch):
    def configure(provider: str, *, host="", username="", password=""):
        monkeypatch.setattr(settings, "email_provider", provider)
        monkeypatch.setattr(settings, "smtp_host", host)
        monkeypatch.setattr(settings, "smtp_username", username)
        monkeypatch.setattr(settings, "smtp_password", password)

    return configure


CREDS = dict(host="smtp.example.com", username="user", password="secret")


# --- The value is read the way a person typed it -----------------------------

@pytest.mark.parametrize("value", ["smtp", "SMTP", "Smtp", " smtp ", "smtp\n"])
def test_a_stray_capital_or_space_still_means_smtp(email_settings, value):
    """A typo in a dashboard field is not a decision to send no email."""
    email_settings(value, **CREDS)

    assert normalized_email_provider() == "smtp"
    assert isinstance(build_email_provider(), SMTPEmailProvider)


def test_an_unset_value_is_the_console(email_settings):
    email_settings("")
    assert isinstance(build_email_provider(), ConsoleEmailProvider)


# --- Delivery is a property of the provider, not of a string -----------------

def test_the_console_reports_that_it_delivers_nothing(email_settings):
    email_settings("console")
    assert build_email_provider().delivers is False


def test_configured_smtp_reports_that_it_delivers(email_settings):
    email_settings("smtp", **CREDS)
    assert build_email_provider().delivers is True


@pytest.mark.parametrize("value", ["resend", "sendgrid", "postmark", "typo123"])
def test_a_provider_triplet_does_not_implement_delivers_nothing(email_settings, value):
    """The exact hole: these are not the word "console", and used to pass."""
    email_settings(value)

    provider = build_email_provider()
    assert provider.delivers is False


def test_half_configured_smtp_delivers_nothing(email_settings):
    email_settings("smtp", host="smtp.example.com")  # no username or password

    assert build_email_provider().delivers is False


# --- A mail problem is never an outage ---------------------------------------

@pytest.mark.parametrize(
    "value,creds",
    [
        ("console", {}),
        ("resend", {}),
        ("typo123", {}),
        ("smtp", {}),
        ("smtp", dict(host="smtp.example.com")),
    ],
)
def test_no_configuration_makes_building_a_provider_raise(email_settings, value, creds):
    """Whatever is in the variable, resolving it must return something.

    Raising here would surface as a 500 on signup, or a crash at startup — and
    an email misconfiguration taking the whole service down is the specific
    mistake this codebase has made twice.
    """
    email_settings(value, **creds)

    provider = build_email_provider()
    assert provider is not None
    assert hasattr(provider, "send_email")


def test_an_unknown_provider_is_reported_loudly(email_settings, caplog):
    import logging

    email_settings("resend")
    with caplog.at_level(logging.ERROR):
        build_email_provider()

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "resend" in logged
    assert "smtp" in logged, "the message should name what is actually available"


def test_half_configured_smtp_names_what_is_missing(email_settings, caplog):
    import logging

    email_settings("smtp", host="smtp.example.com")
    with caplog.at_level(logging.ERROR):
        build_email_provider()

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "SMTP_USERNAME" in logged
    assert "SMTP_PASSWORD" in logged
