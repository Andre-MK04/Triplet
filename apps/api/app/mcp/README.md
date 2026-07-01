# Triplet MCP Plan

Future MCP server name: `triplet-travel-mcp`

Planned tools:

- `search_trips`
- `get_airports`
- `estimate_ground_transfer`
- `explain_trip`
- `save_trip_alert` future
- `get_user_preferences` future
- `update_user_preferences` future

MCP will not replace the backend. It will expose selected backend capabilities to AI agents through a controlled tool surface. The deterministic trip builder remains the source of truth for trip generation, scoring, warnings, tags, and explanations.

Security notes:

- Only safe internal tools should be exposed.
- Travel search tools are read-only and safe for local experimentation.
- User-specific tools will require authentication and authorization later.
- Action tools, including booking, payment, subscriptions, and alerts, must require explicit user confirmation.
- Random external MCP servers should not be trusted by default.
- Development tool endpoints must not be enabled in production.
