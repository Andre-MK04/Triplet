from app.tools.registry import build_default_tool_registry


def build_mcp_tool_mapping():
    """Placeholder showing how internal tools could later map to MCP tools.

    This is not a production MCP server. The real server should add authentication,
    permissions, audit logging, and explicit confirmation for future action tools.
    """
    registry = build_default_tool_registry()
    return {
        tool["name"]: {
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for tool in registry.list_tools()
    }
