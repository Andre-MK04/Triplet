import json
import logging
from collections.abc import Callable
from typing import Any

from app.ai.providers.base import AIProviderConfigError, AIProviderError, AIProviderResult, ToolCallRecord
from app.config import settings

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Claude tool-calling provider with the same contract as OpenAIProvider.

    Accepts OpenAI-style message dicts and function-tool schemas from the
    orchestrator and translates them to the Anthropic Messages API.
    """

    def __init__(self):
        if not settings.anthropic_api_key:
            raise AIProviderConfigError("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic.")
        try:
            import anthropic
        except ImportError as exc:
            raise AIProviderConfigError("The anthropic Python package is not installed.") from exc

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=30)
        self.model = settings.anthropic_model
        self.max_tokens = settings.anthropic_max_tokens

    def run_chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        max_tool_calls: int,
    ) -> AIProviderResult:
        system = "\n\n".join(
            str(message["content"]) for message in messages if message.get("role") == "system"
        )
        working_messages: list[dict[str, Any]] = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message.get("role") != "system"
        ]
        anthropic_tools = [convert_tool_schema(tool) for tool in tools]
        records: list[ToolCallRecord] = []
        warnings: list[str] = []

        while True:
            response = self._create_message(system, working_messages, anthropic_tools)
            text = "".join(block.text for block in response.content if block.type == "text")
            tool_uses = [block for block in response.content if block.type == "tool_use"]

            if not tool_uses:
                return AIProviderResult(
                    message=text,
                    toolCallsUsed=len(records),
                    toolCalls=records,
                    warnings=warnings,
                )

            working_messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for block in tool_uses:
                if len(records) >= max_tool_calls:
                    warnings.append(f"AI tool call limit reached at {max_tool_calls}.")
                    return AIProviderResult(
                        message="I reached the tool-call limit before finishing the search.",
                        toolCallsUsed=len(records),
                        toolCalls=records,
                        warnings=warnings,
                    )

                arguments = dict(block.input or {})
                record = ToolCallRecord(name=block.name, arguments=arguments)
                try:
                    output = tool_executor(block.name, arguments)
                    record.output = output
                    content = json.dumps(output, default=str)
                except Exception as exc:  # noqa: BLE001 - tool errors are returned to the model for correction.
                    record.error = str(exc)
                    content = json.dumps({"error": str(exc)})
                records.append(record)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": bool(record.error),
                    }
                )
            working_messages.append({"role": "user", "content": tool_results})

    def _create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ):
        try:
            return self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system or None,
                messages=messages,
                tools=tools or None,
            )
        except Exception as exc:  # noqa: BLE001 - normalize SDK exceptions for orchestrator fallback.
            logger.warning(
                "anthropic_message_failed model=%s error_type=%s message=%s",
                self.model,
                type(exc).__name__,
                safe_anthropic_error_message(exc),
            )
            raise AIProviderError("Anthropic request failed.") from exc


def convert_tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """OpenAI function-tool schema → Anthropic tool schema."""
    function = tool.get("function") or tool
    return {
        "name": function["name"],
        "description": function.get("description", ""),
        "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
    }


def safe_anthropic_error_message(exc: Exception) -> str:
    message = getattr(exc, "message", None) or str(exc)
    return " ".join(str(message).split())[:500]
