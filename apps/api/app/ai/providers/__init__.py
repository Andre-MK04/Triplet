from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import AIProvider, AIProviderConfigError, AIProviderError, AIProviderResult, ToolCallRecord
from app.ai.providers.openai_provider import OpenAIProvider
from app.config import settings

SUPPORTED_AI_PROVIDERS = ("openai", "anthropic")


def build_ai_provider() -> AIProvider:
    name = settings.ai_provider.lower()
    if name == "openai":
        return OpenAIProvider()
    if name == "anthropic":
        return AnthropicProvider()
    raise AIProviderConfigError(
        f"Unsupported AI provider '{name}'. Supported: {', '.join(SUPPORTED_AI_PROVIDERS)}."
    )


def active_ai_model() -> str:
    return settings.anthropic_model if settings.ai_provider.lower() == "anthropic" else settings.openai_model


__all__ = [
    "AIProvider",
    "AIProviderConfigError",
    "AIProviderError",
    "AIProviderResult",
    "AnthropicProvider",
    "OpenAIProvider",
    "SUPPORTED_AI_PROVIDERS",
    "ToolCallRecord",
    "active_ai_model",
    "build_ai_provider",
]
