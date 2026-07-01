from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel


class AIProviderError(RuntimeError):
    pass


class AIProviderConfigError(AIProviderError):
    pass


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]
    output: Any | None = None
    error: str | None = None


class AIProviderResult(BaseModel):
    message: str
    toolCallsUsed: int = 0
    toolCalls: list[ToolCallRecord] = []
    warnings: list[str] = []


class AIProvider(Protocol):
    def run_chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        max_tool_calls: int,
    ) -> AIProviderResult:
        ...
