import json
import logging
from collections.abc import Callable
from typing import Any

from app.ai.providers.base import AIProviderConfigError, AIProviderError, AIProviderResult, ToolCallRecord
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider:
    def __init__(self):
        if not settings.openai_api_key:
            raise AIProviderConfigError("OPENAI_API_KEY is required when AI_ENABLED=true.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIProviderConfigError("The openai Python package is not installed.") from exc

        self.client = OpenAI(api_key=settings.openai_api_key, timeout=30)
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.reasoning_effort = settings.openai_reasoning_effort

    def run_chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Any],
        max_tool_calls: int,
    ) -> AIProviderResult:
        working_messages = list(messages)
        records: list[ToolCallRecord] = []
        warnings: list[str] = []

        while True:
            response = self._create_completion(working_messages, tools)
            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            if not tool_calls:
                return AIProviderResult(
                    message=message.content or "",
                    toolCallsUsed=len(records),
                    toolCalls=records,
                    warnings=warnings,
                )

            assistant_message = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ],
            }
            working_messages.append(assistant_message)

            for tool_call in tool_calls:
                if len(records) >= max_tool_calls:
                    warnings.append(f"AI tool call limit reached at {max_tool_calls}.")
                    return AIProviderResult(
                        message="I reached the tool-call limit before finishing the search.",
                        toolCallsUsed=len(records),
                        toolCalls=records,
                        warnings=warnings,
                    )

                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                record = ToolCallRecord(name=name, arguments=arguments)
                try:
                    output = tool_executor(name, arguments)
                    record.output = output
                    content = json.dumps(output, default=str)
                except Exception as exc:  # noqa: BLE001 - tool errors are returned to the model for correction.
                    record.error = str(exc)
                    content = json.dumps({"error": str(exc)})
                records.append(record)
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": content,
                    }
                )

    def _create_completion(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]):
        kwargs = self._completion_kwargs(messages, tools)

        try:
            return self.client.chat.completions.create(**kwargs)
        except TypeError:
            kwargs.pop("reasoning_effort", None)
            return self.client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize SDK exceptions for orchestrator fallback.
            message = safe_openai_error_message(exc)
            if is_unsupported_parameter_error(message):
                retry_kwargs = self._completion_kwargs(messages, tools)
                retry_kwargs.pop("reasoning_effort", None)
                retry_kwargs.pop("temperature", None)
                try:
                    return self.client.chat.completions.create(**retry_kwargs)
                except Exception as retry_exc:  # noqa: BLE001
                    logger.warning(
                        "openai_chat_completion_failed model=%s error_type=%s message=%s",
                        self.model,
                        type(retry_exc).__name__,
                        safe_openai_error_message(retry_exc),
                    )
                    raise AIProviderError("OpenAI request failed.") from retry_exc

            logger.warning(
                "openai_chat_completion_failed model=%s error_type=%s message=%s",
                self.model,
                type(exc).__name__,
                message,
            )
            raise AIProviderError("OpenAI request failed.") from exc

    def _completion_kwargs(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "tools": tools,
            "tool_choice": "auto",
        }
        if self.reasoning_effort:
            # Some SDK/model combinations ignore or reject reasoning_effort on Chat Completions.
            # Try it first because it is cost-relevant, then safely retry without it if unsupported.
            kwargs["reasoning_effort"] = self.reasoning_effort
        return kwargs


def safe_openai_error_message(exc: Exception) -> str:
    message = getattr(exc, "message", None) or str(exc)
    return " ".join(str(message).split())[:500]


def is_unsupported_parameter_error(message: str) -> bool:
    normalized = message.lower()
    return (
        ("unsupported" in normalized or "not supported" in normalized)
        and ("reasoning_effort" in normalized or "temperature" in normalized or "parameter" in normalized)
    )
