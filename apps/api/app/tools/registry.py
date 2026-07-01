from typing import Any

from pydantic import BaseModel, ValidationError

from app.tools.base import Tool, ToolContext


class ToolNotFoundError(KeyError):
    pass


class ToolValidationError(ValueError):
    def __init__(self, tool_name: str, errors: list[dict[str, Any]]):
        self.tool_name = tool_name
        self.errors = errors
        super().__init__(f"Invalid input for tool '{tool_name}'.")


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_model.model_json_schema(),
            }
            for tool in self._tools.values()
        ]

    def get_tool(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Unknown tool '{name}'.") from exc

    def run_tool(self, name: str, input_data: dict[str, Any] | BaseModel, context: ToolContext) -> Any:
        tool = self.get_tool(name)
        raw_input = input_data.model_dump() if isinstance(input_data, BaseModel) else input_data
        try:
            validated_input = tool.input_model.model_validate(raw_input)
        except ValidationError as exc:
            raise ToolValidationError(name, exc.errors()) from exc

        result = tool.run(validated_input, context)
        if tool.output_model and not isinstance(result, tool.output_model):
            return tool.output_model.model_validate(result)
        return result


def build_default_tool_registry() -> ToolRegistry:
    from app.tools.travel_tools import default_travel_tools

    registry = ToolRegistry()
    for tool in default_travel_tools():
        registry.register(tool)
    return registry
