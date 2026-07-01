from types import SimpleNamespace

from app.ai.providers.openai_provider import OpenAIProvider, is_unsupported_parameter_error


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise RuntimeError("Unsupported parameter: 'reasoning_effort'")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[], content="ok"))])


def test_openai_provider_retries_without_optional_unsupported_params(monkeypatch):
    provider = object.__new__(OpenAIProvider)
    completions = FakeCompletions()
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider.model = "gpt-5.4-mini"
    provider.temperature = 0.2
    provider.reasoning_effort = "low"

    response = provider._create_completion([{"role": "user", "content": "hello"}], [])

    assert response.choices[0].message.content == "ok"
    assert "reasoning_effort" in completions.calls[0]
    assert "temperature" in completions.calls[0]
    assert "reasoning_effort" not in completions.calls[1]
    assert "temperature" not in completions.calls[1]


def test_openai_provider_detects_not_supported_reasoning_effort_message():
    message = (
        "Function tools with reasoning_effort are not supported for gpt-5.4-mini "
        "in /v1/chat/completions. Please use /v1/responses instead."
    )

    assert is_unsupported_parameter_error(message) is True
