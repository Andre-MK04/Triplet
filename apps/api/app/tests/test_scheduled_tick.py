from datetime import datetime

from app.scheduled import tick


def _patch_jobs(monkeypatch, calls):
    monkeypatch.setattr(tick, "refresh_deals", lambda: calls.append("deals") or {"upserted": 5})
    monkeypatch.setattr(tick, "run_due_alerts", lambda: calls.append("alerts") or [1, 2])
    monkeypatch.setattr(tick, "run_retention_cleanup", lambda: calls.append("retention") or {"auditDeleted": 1})


def test_tick_runs_deals_and_alerts_every_hour_but_retention_only_at_configured_hour(monkeypatch):
    monkeypatch.setattr(tick, "RETENTION_HOUR", 3)

    calls: list[str] = []
    _patch_jobs(monkeypatch, calls)
    off_hour = tick.run_tick(now=datetime(2026, 8, 1, 10, 0))
    assert calls == ["deals", "alerts"]  # no retention at 10:00
    assert off_hour["alertsRun"] == 2 and off_hour["retention"] is None

    calls.clear()
    _patch_jobs(monkeypatch, calls)
    on_hour = tick.run_tick(now=datetime(2026, 8, 1, 3, 0))
    assert calls == ["deals", "alerts", "retention"]  # retention fires at 03:00
    assert on_hour["retention"] == {"auditDeleted": 1}


def test_tick_isolates_a_failing_job(monkeypatch):
    monkeypatch.setattr(tick, "RETENTION_HOUR", 3)

    def boom():
        raise RuntimeError("provider down")

    monkeypatch.setattr(tick, "refresh_deals", boom)
    monkeypatch.setattr(tick, "run_due_alerts", lambda: [1])
    summary = tick.run_tick(now=datetime(2026, 8, 1, 10, 0))

    # Deals failed but alerts still ran, and the failure is reported not raised.
    assert summary["alertsRun"] == 1
    assert any("deals" in e for e in summary["errors"])
