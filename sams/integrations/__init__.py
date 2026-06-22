"""Integrations — external systems adapted into SAMS as tools + events (spec 9).

Built-in adapters: GitHub/version control, MCP servers, and webhooks. Each maps
an external system's activity onto the Event Bus and exposes callable tools.
"""

from .github import GitHubSync
from .mcp import MCPConnector
from .webhooks import WebhookRouter

__all__ = ["GitHubSync", "MCPConnector", "WebhookRouter"]
