from fastapi.testclient import TestClient

from app.ai.providers import AIProviderConfigError, AIProviderResult
from app.ai import orchestrator
from app.ai.orchestrator import sanitize_ai_message
from app.config import settings
from app.database import get_db
from app.main import app
from app.rate_limit import clear_rate_limits


def override_db(db_session):
    def _override_get_db():
        yield db_session

    return _override_get_db


def test_get_tools_works_only_when_enabled(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", True)
    enabled_response = client.get("/tools")
    assert enabled_response.status_code == 200

    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", False)
    disabled_response = client.get("/tools")
    app.dependency_overrides.clear()

    assert disabled_response.status_code == 404


def test_run_tool_works_only_when_enabled(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    payload = {"toolName": "get_airports", "input": {"originCandidatesOnly": True}}

    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", True)
    enabled_response = client.post("/tools/run", json=payload)
    assert enabled_response.status_code == 200
    assert enabled_response.json()["airports"]

    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", False)
    disabled_response = client.post("/tools/run", json=payload)
    app.dependency_overrides.clear()

    assert disabled_response.status_code == 404


def test_ai_parse_trip_intent_route_returns_parsed_data():
    client = TestClient(app)

    response = client.post(
        "/ai/parse-trip-intent",
        json={
            "message": "Find me a cheap 5 to 7 day trip in August from Vienna or Zagreb under 180 euros. I like two cities."
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data["originAirports"]) == {"VIE", "ZAG"}
    assert data["tripStyle"] == "two nearby cities"
    assert data["parsedSearch"] is not None


def test_ai_search_preview_returns_results_when_intent_is_complete(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)

    response = client.post(
        "/ai/search-preview",
        json={
            "message": "Find me a cheap 5 to 7 day trip in July from Vienna or Zagreb under 180 euros. I like two cities."
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["intent"]["parsedSearch"] is not None
    assert data["results"]["trips"]


def test_ai_search_disabled_uses_rule_based_parser_and_search_trips(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "ai_enabled", False)

    response = client.post(
        "/ai/search",
        json={
            "message": "Find me a cheap 5 to 7 day trip in July from Vienna or Zagreb under 180 euros. I like two cities."
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["parsedRequest"]["maxBudget"] == 180
    assert set(data["parsedRequest"]["originAirports"]) == {"VIE", "ZAG"}
    assert data["trips"]
    assert data["aiMetadata"]["fallbackUsed"] is True
    assert data["aiMetadata"]["aiProvider"] == "rule-based"


def test_ai_parse_returns_missing_fields_for_vague_request(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "ai_enabled", False)

    response = client.post("/ai/parse", json={"message": "Find me something cheap from Vienna"})

    assert response.status_code == 200
    data = response.json()
    assert data["parsedRequest"] is None
    assert "dateRange" in data["missingFields"]
    assert "tripLength" in data["missingFields"]


def test_ai_search_enabled_missing_key_falls_back(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", None)

    response = client.post(
        "/ai/search",
        json={"message": "from Vienna or Zagreb under 180 euros in July for 5 to 7 days"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["aiMetadata"]["fallbackUsed"] is True
    assert data["trips"]
    assert any("OPENAI_API_KEY" in warning for warning in data["aiMetadata"]["warnings"])


def test_ai_search_uses_search_trips_tool_output(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeOpenAIProvider:
        def run_chat_with_tools(self, messages, tools, tool_executor, max_tool_calls):
            output = tool_executor(
                "search_trips",
                {
                    "originAirports": ["VIE", "ZAG"],
                    "startDate": "2026-07-01",
                    "endDate": "2026-07-31",
                    "minTripLengthDays": 5,
                    "maxTripLengthDays": 7,
                    "maxBudget": 180,
                    "maxGroundTransferHours": 4,
                    "tripStyle": "two nearby cities",
                    "directOnly": False,
                    "includeBaggage": False,
                },
            )
            assert "trips" in output
            return AIProviderResult(message="Here are deterministic trip results.", toolCallsUsed=1)

    monkeypatch.setattr(orchestrator, "OpenAIProvider", FakeOpenAIProvider)

    response = client.post(
        "/ai/search",
        json={"message": "Find trips from Vienna or Zagreb in July under 180 euros for 5 to 7 days."},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["aiMetadata"]["fallbackUsed"] is False
    assert data["aiMetadata"]["toolCallsUsed"] == 1
    assert data["trips"]
    assert data["message"] == "Here are deterministic trip results."


def test_ai_search_sanitizes_markdown_message(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class MarkdownOpenAIProvider:
        def run_chat_with_tools(self, messages, tools, tool_executor, max_tool_calls):
            tool_executor(
                "search_trips",
                {
                    "originAirports": ["VIE", "ZAG"],
                    "startDate": "2026-07-01",
                    "endDate": "2026-07-31",
                    "minTripLengthDays": 5,
                    "maxTripLengthDays": 7,
                    "maxBudget": 180,
                    "maxGroundTransferHours": 4,
                    "tripStyle": "two nearby cities",
                    "directOnly": False,
                    "includeBaggage": False,
                },
            )
            return AIProviderResult(
                message=(
                    "### Best cheap picks\n"
                    "1. **Vienna -> Palma** is a strong option.\n"
                    "2. __Zagreb -> Alicante__ is another option.\n"
                    "| route | price |"
                ),
                toolCallsUsed=1,
            )

    monkeypatch.setattr(orchestrator, "OpenAIProvider", MarkdownOpenAIProvider)

    response = client.post(
        "/ai/search",
        json={"message": "Find trips from Vienna or Zagreb in July under 180 euros for 5 to 7 days."},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    message = response.json()["message"]
    assert "###" not in message
    assert "**" not in message
    assert "__" not in message
    assert "|" not in message
    assert len(message) <= 400


def test_ai_search_provider_error_falls_back(db_session, monkeypatch):
    app.dependency_overrides[get_db] = override_db(db_session)
    client = TestClient(app)
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FailingOpenAIProvider:
        def __init__(self):
            raise AIProviderConfigError("Provider failed cleanly.")

    monkeypatch.setattr(orchestrator, "OpenAIProvider", FailingOpenAIProvider)

    response = client.post(
        "/ai/search",
        json={"message": "from Vienna or Zagreb under 180 euros in July for 5 to 7 days"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["aiMetadata"]["fallbackUsed"] is True
    assert data["trips"]


def test_sanitize_ai_message_removes_markdown_and_limits_length():
    message = (
        "### Best cheap picks\n"
        "1. **Vienna -> Palma** is a strong option.\n"
        "2. __Zagreb -> Alicante__ has a train transfer.\n"
        "- `Do not show code`\n"
        "| route | price |\n"
        + "Extra detail. " * 80
    )

    cleaned = sanitize_ai_message(message)

    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "__" not in cleaned
    assert "`" not in cleaned
    assert "|" not in cleaned
    assert len(cleaned) <= 400


def test_provider_smoke_test_disabled_when_dev_endpoints_disabled(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", False)

    response = client.get("/providers/smoke-test")

    assert response.status_code == 404


def test_provider_smoke_test_database_mode(db_session, monkeypatch):
    app.dependency_overrides.clear()
    clear_rate_limits()
    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", True)
    monkeypatch.setattr(settings, "flight_provider", "database")
    monkeypatch.setattr(settings, "skyscanner_api_enabled", False)
    monkeypatch.setattr(settings, "skyscanner_api_key", "secret-api-key")
    monkeypatch.setattr(settings, "skyscanner_media_partner_id", "partner-id")

    # Smoke-test uses the app SessionLocal, so assert response shape rather than
    # coupling this test to external PostgreSQL availability.
    client = TestClient(app)
    response = client.get("/providers/smoke-test")

    assert response.status_code == 200
    assert response.json()["configuredProvider"] == "database"
    assert "database" in response.json()
    assert "secret-api-key" not in response.text


def test_provider_smoke_test_hybrid_warns_without_live_provider_config(monkeypatch):
    clear_rate_limits()
    client = TestClient(app)
    monkeypatch.setattr(settings, "enable_dev_tool_endpoints", True)
    monkeypatch.setattr(settings, "flight_provider", "hybrid")
    monkeypatch.setattr(settings, "live_flight_provider", "skyscanner")
    monkeypatch.setattr(settings, "skyscanner_api_enabled", False)
    monkeypatch.setattr(settings, "skyscanner_api_key", None)
    monkeypatch.setattr(settings, "skyscanner_media_partner_id", None)

    response = client.get("/providers/smoke-test")

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["provider"] == "skyscanner"
    assert body["result"]["configured"] is False
    assert body["result"]["apiOk"] is False
    assert body["overallStatus"] == "warning"
    assert "skyscanner" in " ".join(body["warnings"]).lower()
