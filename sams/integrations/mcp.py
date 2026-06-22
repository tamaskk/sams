"""MCP (Model Context Protocol) connector (spec 9.3).

Connecting an MCP server makes its tools callable by permitted agents as
``mcp.<server>.<tool>`` — no adapter code. This reference connector registers
the declared tools into the global :class:`ToolRegistry`; transport (stdio/url)
is pluggable. Calls are subject to the same permission checks as native tools.
"""

from __future__ import annotations

import logging
from typing import Any

from ..sdk.registry import ToolRegistry, ToolSpec

log = logging.getLogger("sams.integrations.mcp")


class MCPConnector:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry.global_instance()
        self.servers: dict[str, dict[str, Any]] = {}

    def connect(self, name: str, *, transport: str = "stdio", command: str | None = None,
                url: str | None = None, tools: list[str] | None = None) -> list[str]:
        """Register an MCP server and expose its tools as ``mcp.<server>.<tool>``."""
        self.servers[name] = {"transport": transport, "command": command, "url": url}
        registered: list[str] = []
        for tool_name in (tools or ["list", "read", "call"]):
            tool_id = f"mcp.{name}.{tool_name}"

            async def _call(ctx, *args, _tid=tool_id, **kwargs) -> dict[str, Any]:
                # Placeholder transport: a real connector forwards to the server.
                await ctx.emit("integration.mcp.called", {"tool": _tid, "args": kwargs})
                return {"tool": _tid, "args": kwargs, "result": "ok"}

            self.registry.register(ToolSpec(
                id=tool_id, fn=_call, requires_permission=f"tools:{tool_id}",
                description=f"MCP tool {tool_name} on server {name}",
            ))
            registered.append(tool_id)
        log.info("connected MCP server %s (%d tools)", name, len(registered))
        return registered

    def connect_from_config(self, mcp_config: dict[str, Any]) -> None:
        for server in mcp_config.get("servers", []):
            self.connect(
                server["name"],
                transport=server.get("type", "stdio"),
                command=server.get("command"),
                url=server.get("url"),
                tools=server.get("tools"),
            )
