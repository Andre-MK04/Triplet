from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai.providers import AIProviderConfigError, build_ai_provider
from app.ai.providers.anthropic_provider import AnthropicProvider, convert_tool_schema
from app.config import settings
from app.database import get_db
from app.main import app


def text_block(text: str):
    return SimpleNamespace(type="text", text=text)

def tool_use_block(block_id: str, name: str, arguments: dict):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=arguments)


def response(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


class FakeMessagesApi:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def make_provider(monkeypatch, responses) -> tuple[AnthropicProvider, FakeMessagesApi]:
    monkeypatch.setattr(settings, "anthropic_api_key", "test-anthropic-key")
    fake_api = FakeMessagesApi(responses)

    import anthropic

    monkeypatch.setattr(
        anthropic, "Anthropic", lambda **kwargs: SimpleNamespace(messages=fake_api)
    )
    return AnthropicProvider(), fake_api


def test_anthropic_provider_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    with pytest.raises(AIProviderConfigError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()


def test_convert_tool_schema_maps_openai_function_format():
    openai_tool = {
        "type": "function",
        "function": {
            "name": "search_trips",
            "description": "Search trips.",
            "parameters": {"type": "object", "properties": {"maxBudget": {"type": "number"}}},
        },
    }

    converted = convert_tool_schema(openai_tool)

    assert converted["name"] == "search_trips"
    assert converted["input_schema"]["properties"]["maxBudget"]["type"] == "number"


def test_anthropic_provider_executes_tool_calls_and_returns_text(monkeypatch):
    provider, fake_api = make_provider(
        monkeypatch,
        [
            response([tool_use_block("tu_1", "search_trips", {"maxBudget": 150})], stop_reason="tool_use"),
            response([text_block("Found 3 trips under €150.")]),
        ],
    )
    executed = {}

    def executor(name, arguments):
        executed["name"] = name
        executed["arguments"] = arguments
        return {"trips": []}

    result = provider.run_chat_with_tools(
        messages=[
            {"role": "system", "content": "You are Triplet."},
            {"role": "user", "content": "Find me trips under 150."},
        ],
        tools=[{"type": "function", "function": {"name": "search_trips", "parameters": {"type": "object"}}}],
        tool_executor=executor,
        max_tool_calls=3,
    )

    assert executed == {"name": "search_trips", "arguments": {"maxBudget": 150}}
    assert result.message == "Found 3 trips under €150."
    assert result.toolCallsUsed == 1
    first_call = fake_api.calls[0]
    assert first_call["system"] == "You are Triplet."
    assert first_call["tools"][0]["name"] == "search_trips"
    # Second call must include the tool result for the model to read.
    follow_up = fake_api.calls[1]["messages"][-1]
    assert follow_up["role"] == "user"
    assert follow_up["content"][0]["type"] == "tool_result"


def test_anthropic_provider_enforces_tool_call_limit(monkeypatch):
    endless_tool_use = response(
        [tool_use_block("tu_x", "search_trips", {})], stop_reason="tool_use"
    )
    provider, _ = make_provider(monkeypatch, [endless_tool_use, endless_tool_use, endless_tool_use])

    result = provider.run_chat_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        tool_executor=lambda name, arguments: {"ok": True},
        max_tool_calls=2,
    )

    assert result.toolCallsUsed == 2
    assert any("limit" in warning for warning in result.warnings)


def test_build_ai_provider_selects_anthropic(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    provider = build_ai_provider()

    assert isinstance(provider, AnthropicProvider)


def test_ai_search_with_anthropic_and_no_key_falls_back(db_session, monkeypatch):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    result = client.post(
        "/ai/search",
        json={"message": "from Vienna or Zagreb under 180 euros in July for 5 to 7 days"},
    )
    app.dependency_overrides.clear()

    assert result.status_code == 200
    data = result.json()
    assert data["aiMetadata"]["fallbackUsed"] is True
    assert data["trips"]
    assert any("ANTHROPIC_API_KEY" in warning for warning in data["aiMetadata"]["warnings"])
