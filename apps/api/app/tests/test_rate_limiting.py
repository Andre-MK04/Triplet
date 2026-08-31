"""Abuse protection on the endpoints that cost money.

Two things are defended here. Every route that reaches a language model or a
paid flight provider carries a budget — the danger being a cheap unguarded
endpoint that calls the same expensive machinery as a guarded one. And the
service as a whole has a daily model ceiling, so a loop or a distributed abuser
cannot run up an unbounded bill overnight.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app
from app.security import (
    RateLimitCategory,
    RateLimitExceeded,
    check_rate_limit,
    consume_ai_call,
    reset_ai_budget,
    reset_rate_limits,
)


class FakeRequest:
    def __init__(self, ip: str = "203.0.113.9"):
        self.headers: dict[str, str] = {}
        self.client = type("C", (), {"host": ip})()


@pytest.fixture(autouse=True)
def clean_limits():
    reset_rate_limits()
    reset_ai_budget()
    yield
    reset_rate_limits()
    reset_ai_budget()


def exhaust(category: RateLimitCategory, request: FakeRequest, user_id: str | None = None) -> int:
    allowed = 0
    for _ in range(1000):
        try:
            check_rate_limit(category, request, user_id)
            allowed += 1
        except RateLimitExceeded:
            return allowed
    raise AssertionError(f"{category} never limited")


def test_each_category_has_its_own_budget():
    request = FakeRequest()

    ai = exhaust(RateLimitCategory.AI, request)
    search = exhaust(RateLimitCategory.SEARCH, request)

    assert ai == settings.ai_search_rate_limit_max_attempts
    assert search == settings.trips_search_rate_limit_max_attempts
    # Spending the AI budget must not spend the search budget.
    assert ai != search or settings.ai_search_rate_limit_max_attempts == settings.trips_search_rate_limit_max_attempts


def test_a_limited_caller_is_told_how_long_to_wait():
    request = FakeRequest()
    exhaust(RateLimitCategory.AI, request)

    with pytest.raises(RateLimitExceeded) as raised:
        check_rate_limit(RateLimitCategory.AI, request)

    assert raised.value.retry_after_seconds >= 1


def test_callers_are_limited_separately():
    exhaust(RateLimitCategory.AI, FakeRequest("203.0.113.1"))

    # A different address still has its own budget.
    check_rate_limit(RateLimitCategory.AI, FakeRequest("203.0.113.2"))


def test_an_authenticated_caller_cannot_buy_budget_by_changing_address():
    """Identity beats address, so rotating IPs does not reset an account's limit."""
    exhaust(RateLimitCategory.AI, FakeRequest("203.0.113.1"), user_id="user-1")

    with pytest.raises(RateLimitExceeded):
        check_rate_limit(RateLimitCategory.AI, FakeRequest("198.51.100.7"), user_id="user-1")


def test_a_spoofed_forwarding_header_is_ignored_when_not_behind_a_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    request = FakeRequest("203.0.113.1")
    request.headers["x-forwarded-for"] = "1.2.3.4"
    exhaust(RateLimitCategory.AI, request)

    spoofed = FakeRequest("203.0.113.1")
    spoofed.headers["x-forwarded-for"] = "5.6.7.8"
    with pytest.raises(RateLimitExceeded):
        check_rate_limit(RateLimitCategory.AI, spoofed)


def test_the_daily_model_ceiling_stops_runaway_spend(monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_request_limit", 3)

    assert [consume_ai_call() for _ in range(5)] == [True, True, True, False, False]


def test_no_ceiling_when_it_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_request_limit", 0)

    assert all(consume_ai_call() for _ in range(50))


# ---------------------------------------------------------------- HTTP routes

@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("path", "payload", "category"),
    [
        ("/ai/parse", {"message": "a week in Rome from Vienna"}, RateLimitCategory.AI),
        ("/ai/search", {"message": "a week in Rome from Vienna"}, RateLimitCategory.AI),
        ("/ai/search-preview", {"message": "a week in Rome from Vienna"}, RateLimitCategory.SEARCH),
        ("/ai/parse-trip-intent", {"message": "a week in Rome"}, RateLimitCategory.CHEAP),
    ],
)
def test_every_ai_route_is_budgeted(client, path, payload, category):
    """/ai/parse reached a model and /ai/search-preview ran a provider search,
    both with no limit at all, while the endpoint they shadowed was protected."""
    request = FakeRequest("testclient")
    exhaust(category, request)

    response = client.post(path, json=payload)

    assert response.status_code == 429, f"{path} was not limited"
    assert response.headers.get("Retry-After")


def test_a_limited_response_is_not_cached(client):
    exhaust(RateLimitCategory.AI, FakeRequest("testclient"))

    response = client.post("/ai/search", json={"message": "a week in Rome from Vienna"})

    assert response.headers.get("Cache-Control") == "no-store"
