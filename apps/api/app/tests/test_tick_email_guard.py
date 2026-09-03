"""The scheduled tick must not spend watch cooldowns on undelivered mail.

The cron service runs `app.scheduled.tick` and never starts FastAPI, so the
production configuration guard in `app.main` has never applied to it. That
mattered because the alert runner claims a watch's notification slot *before*
sending and marks it notified afterwards regardless of whether a mailbox
received anything.

So a cron with a console provider would walk every due watch, advance each
cooldown, and record a delivery — and that deal would never be re-sent once
the configuration was fixed. The watch history would say the alert went out.
"""

import pytest

from app.config import settings
from app.scheduled import tick


@pytest.fixture()
def stub_jobs(monkeypatch):
    """Neutralise everything except the decision under test."""
    calls = {"alerts": 0}

    monkeypatch.setattr(tick, "refresh_deals", lambda: {"upserted": 0})
    monkeypatch.setattr(tick, "refresh_featured_deals", lambda: {"ok": True})
    monkeypatch.setattr(tick, "run_retention_cleanup", lambda: {"ok": True})

    def fake_alerts():
        calls["alerts"] += 1
        return []

    monkeypatch.setattr(tick, "run_due_alerts", fake_alerts)
    return calls


def set_delivery(monkeypatch, *, delivers: bool, strict: bool):
    class Provider:
        def __init__(self):
            self.delivers = delivers

    monkeypatch.setattr(tick, "build_email_provider", lambda: Provider())
    monkeypatch.setattr(settings, "email_require_real_provider", strict)


def test_a_deployment_demanding_real_email_skips_the_pass(stub_jobs, monkeypatch):
    """Nothing is spent when nothing can be delivered."""
    set_delivery(monkeypatch, delivers=False, strict=True)

    summary = tick.run_tick()

    assert stub_jobs["alerts"] == 0, "the alert pass ran and burned cooldowns"
    assert any("alerts" in err for err in summary["errors"])


def test_the_other_jobs_still_run_when_alerts_are_skipped(stub_jobs, monkeypatch):
    """Email is one feature. It does not get to stop cache warming.

    This codebase has twice taken production down over an email problem; the
    rule since is that a mail failure degrades the mail, not the service.
    """
    set_delivery(monkeypatch, delivers=False, strict=True)

    summary = tick.run_tick()

    assert summary["deals"] is not None
    assert summary["featuredDeals"] is not None


def test_alerts_run_normally_when_email_is_deliverable(stub_jobs, monkeypatch):
    set_delivery(monkeypatch, delivers=True, strict=True)

    tick.run_tick()

    assert stub_jobs["alerts"] == 1


def test_local_work_still_exercises_the_alert_path(stub_jobs, monkeypatch, caplog):
    """Without the strict flag the pass still runs — that is how it gets tested.

    But it says what it is about to cost, because a warning nobody reads is
    still better than a cooldown nobody can explain.
    """
    import logging

    set_delivery(monkeypatch, delivers=False, strict=False)

    with caplog.at_level(logging.WARNING):
        tick.run_tick()

    assert stub_jobs["alerts"] == 1
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "cooldown" in logged
